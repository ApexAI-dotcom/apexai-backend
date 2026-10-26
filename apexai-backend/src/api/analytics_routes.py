#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Analytics de navigation

Ingestion légère des vues de page + temps passé (parcours utilisateur),
et agrégations pour le back-office : pages les plus vues, temps moyen,
répartition par tier, série temporelle. Objectif : comprendre le parcours
des pilotes pour orienter le produit.

Confidentialité : on ne stocke jamais d'URL avec paramètres sensibles ;
les chemins sont normalisés (les IDs deviennent ":id").
"""

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from supabase import Client, create_client

from .auth import get_current_user
from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

SUPABASE_URL = os.getenv("SUPABASE_URL") or getattr(settings, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
)

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_SERVICE_ROLE_KEY not in ("", "ton_service_role_key"):
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _normalize_path(path: str) -> str:
    """Réduit les chemins avec identifiants pour l'agrégation (/analysis/abc -> /analysis/:id)."""
    p = (path or "/").split("?")[0].split("#")[0]
    p = re.sub(r"/[0-9a-fA-F-]{8,}", "/:id", p)      # UUID / hash
    p = re.sub(r"/\d+", "/:id", p)                    # ids numériques
    return p[:120] or "/"


class TrackEvent(BaseModel):
    path: str
    # Le front envoie « eventType » : sans cet alias, chaque départ de page
    # était enregistré comme une vue (vues gonflées d'environ 60 %).
    event_type: str = Field(default="view", alias="eventType")
    duration_ms: Optional[int] = Field(default=None, alias="durationMs")
    # Identifiant du navigateur (persistant) et de la visite (30 min d'inactivité).
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    visit_id: Optional[str] = Field(default=None, alias="visitId")
    user_id: Optional[str] = Field(default=None, alias="userId")
    referrer: Optional[str] = None
    tier: Optional[str] = None
    device: Optional[str] = None
    utm_source: Optional[str] = Field(default=None, alias="utmSource")
    utm_medium: Optional[str] = Field(default=None, alias="utmMedium")
    utm_campaign: Optional[str] = Field(default=None, alias="utmCampaign")
    tz: Optional[str] = None
    lang: Optional[str] = None

    class Config:
        populate_by_name = True


def _resolve_user(authorization: Optional[str]) -> Optional[str]:
    """User optionnel : le tracking marche aussi pour les visiteurs anonymes.
    Décodage best-effort du JWT — on ne bloque jamais le tracking sur l'auth."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        return None
    try:
        import jwt as _jwt
        secret = getattr(settings, "SUPABASE_JWT_SECRET", "") or ""
        if secret:
            try:
                payload = _jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
                return payload.get("sub")
            except Exception:
                pass  # jetons signés par clé asymétrique : lecture simple ci-dessous
        # Lecture non vérifiée du sub : usage statistique seulement, jamais d'accès.
        payload = _jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        return payload.get("sub")
    except Exception:
        return None


_UUID = re.compile(r"^[0-9a-fA-F-]{36}$")


def _clip(value: Optional[str], n: int) -> Optional[str]:
    return (value or "")[:n] or None


@router.post("/track")
async def track(event: TrackEvent, authorization: Optional[str] = Header(None)):
    """Enregistre une vue de page ou un départ (avec temps passé). Jamais bloquant."""
    if not supabase:
        return {"ok": False}
    if event.event_type not in ("view", "leave"):
        return {"ok": False}
    try:
        user_id = _resolve_user(authorization)
        # sendBeacon (départ de page) ne peut pas porter d'en-tête : le compte
        # est alors repris du corps, au format UUID seulement.
        if not user_id and event.user_id and _UUID.match(event.user_id):
            user_id = event.user_id
        device = (event.device or "").lower()
        supabase.table("page_events").insert({
            "user_id": user_id,
            "session_id": _clip(event.session_id, 64),
            "visit_id": _clip(event.visit_id, 64),
            "path": _normalize_path(event.path),
            "event_type": event.event_type,
            "duration_ms": int(event.duration_ms) if event.duration_ms and 0 < event.duration_ms < 6 * 3600 * 1000 else None,
            "referrer": _clip(event.referrer, 200),
            "tier": _clip(event.tier, 20),
            "device": device if device in ("mobile", "tablette", "ordinateur") else None,
            "utm_source": _clip(event.utm_source, 60),
            "utm_medium": _clip(event.utm_medium, 60),
            "utm_campaign": _clip(event.utm_campaign, 80),
            "tz": _clip(event.tz, 40),
            "lang": _clip(event.lang, 10),
        }).execute()
        return {"ok": True}
    except Exception as e:
        logger.warning(f"analytics track failed: {e}")
        return {"ok": False}


@router.get("/overview")
async def analytics_overview(days: int = 14, current_user: str = Depends(get_current_user)):
    """[ADMIN] Agrégats de navigation sur la fenêtre demandée."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Service indisponible")
    # Permission 'stats' via le système de rôles
    try:
        from .admin_panel_routes import get_admin_role, PERMISSIONS
        role = get_admin_role(current_user)
        if not role or "stats" not in PERMISSIONS.get(role, set()):
            raise HTTPException(status_code=403, detail="Permission insuffisante.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Permission insuffisante.")

    days = max(1, min(days, 90))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        res = supabase.table("page_events").select("path, event_type, duration_ms, user_id, tier, created_at") \
            .gte("created_at", since).order("created_at", desc=True).limit(20000).execute()
        rows = res.data or []
    except Exception as e:
        logger.error(f"analytics_overview failed: {e}")
        raise HTTPException(status_code=500, detail="Lecture impossible.")

    views = [r for r in rows if r.get("event_type") == "view"]
    leaves = [r for r in rows if r.get("event_type") == "leave" and r.get("duration_ms")]

    # Par page : nombre de vues + temps moyen
    by_path: Dict[str, Dict[str, Any]] = {}
    for r in views:
        p = r["path"]
        by_path.setdefault(p, {"path": p, "views": 0, "total_ms": 0, "timed": 0})
        by_path[p]["views"] += 1
    for r in leaves:
        p = r["path"]
        if p in by_path:
            by_path[p]["total_ms"] += int(r["duration_ms"])
            by_path[p]["timed"] += 1
    top_pages = []
    for d in by_path.values():
        avg = round(d["total_ms"] / d["timed"] / 1000, 1) if d["timed"] else None
        top_pages.append({"path": d["path"], "views": d["views"], "avg_seconds": avg})
    top_pages.sort(key=lambda x: x["views"], reverse=True)

    # Série temporelle : vues par jour
    by_day: Dict[str, int] = {}
    for r in views:
        day = str(r["created_at"])[:10]
        by_day[day] = by_day.get(day, 0) + 1
    timeline = [{"date": k, "views": v} for k, v in sorted(by_day.items())]

    # Répartition par tier (visiteurs vs abonnés)
    by_tier: Dict[str, int] = {}
    for r in views:
        t = (r.get("tier") or "visiteur").lower()
        by_tier[t] = by_tier.get(t, 0) + 1

    # Visiteurs uniques (approx via user_id, anonymes comptés à part)
    unique_users = len({r["user_id"] for r in views if r.get("user_id")})
    anon_views = len([r for r in views if not r.get("user_id")])

    total_timed = [int(r["duration_ms"]) for r in leaves]
    avg_session_s = round(sum(total_timed) / len(total_timed) / 1000, 1) if total_timed else None

    return {
        "window_days": days,
        "totals": {
            "views": len(views),
            "unique_signed_in": unique_users,
            "anonymous_views": anon_views,
            "avg_time_on_page_s": avg_session_s,
        },
        "top_pages": top_pages[:15],
        "timeline": timeline,
        "by_tier": by_tier,
    }


def _team_user_ids() -> List[str]:
    try:
        res = supabase.table("admin_roles").select("user_id").execute()
        return [r["user_id"] for r in (res.data or []) if r.get("user_id")]
    except Exception:
        return []


def _require_stats(current_user: str) -> None:
    try:
        from .admin_panel_routes import get_admin_role, PERMISSIONS
        role = get_admin_role(current_user)
        if not role or "stats" not in PERMISSIONS.get(role, set()):
            raise HTTPException(status_code=403, detail="Permission insuffisante.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Permission insuffisante.")


def _fetch_all(table: str, columns: str, since: Optional[str] = None, cap: int = 100000) -> List[Dict[str, Any]]:
    """Lecture paginée (PostgREST limite chaque réponse à 1 000 lignes)."""
    rows: List[Dict[str, Any]] = []
    page = 1000
    for start in range(0, cap, page):
        q = supabase.table(table).select(columns).order("created_at", desc=False).range(start, start + page - 1)
        if since:
            q = q.gte("created_at", since)
        data = q.execute().data or []
        rows.extend(data)
        if len(data) < page:
            break
    return rows


def load_launch_report(days: int) -> Dict[str, Any]:
    from .launch_analytics import build_launch_report

    now = datetime.now(timezone.utc)
    events = _fetch_all(
        "page_events",
        "session_id, visit_id, user_id, path, event_type, duration_ms, referrer, device, utm_source, utm_campaign, created_at",
    )
    users = supabase.rpc("admin_launch_users", {}).execute().data or []
    since = (now - timedelta(days=2 * days + 1)).isoformat()
    analyses = _fetch_all("analyses", "user_id, created_at", since=since)
    return build_launch_report(events, users, analyses, _team_user_ids(), now, days)


@router.get("/launch")
async def analytics_launch(days: int = 14, current_user: str = Depends(get_current_user)):
    """[ADMIN] Suivi de lancement : visiteurs réels, provenance, parcours, inscrits."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Service indisponible")
    _require_stats(current_user)
    days = max(1, min(days, 90))
    try:
        return load_launch_report(days)
    except Exception as e:
        logger.error(f"analytics_launch failed: {e}")
        raise HTTPException(status_code=500, detail="Lecture impossible.")
