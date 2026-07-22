#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Back-office administrateur

Système de rôles délégables (table admin_roles) :
    owner   : tout, y compris attribuer des rôles à des collaborateurs
    admin   : tout sauf la gestion des rôles
    support : retours pilotes + lecture des stats
    analyst : lecture des stats uniquement

Le rôle est TOUJOURS résolu côté serveur depuis la base : jamais un flag
envoyé par le client. Chaque endpoint déclare la permission qu'il exige.
"""

import logging
import os
import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from .auth import get_current_user
from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-panel"])

SUPABASE_URL = os.getenv("SUPABASE_URL") or getattr(settings, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
)
FOUNDER_EMAIL = (os.getenv("ADMIN_EMAIL") or "moreauy58@gmail.com").strip().lower()

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_SERVICE_ROLE_KEY not in ("", "ton_service_role_key"):
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Permissions par rôle (source de vérité unique)
PERMISSIONS: Dict[str, set] = {
    "owner":   {"stats", "feedback", "promo", "catalog", "circuits", "roles", "users"},
    "admin":   {"stats", "feedback", "promo", "catalog", "circuits", "users"},
    "support": {"stats", "feedback"},
    "analyst": {"stats"},
}
ROLE_LABELS = {
    "owner": "Propriétaire", "admin": "Administrateur",
    "support": "Support", "analyst": "Analyste",
}


def get_admin_role(user_id: str) -> Optional[str]:
    """Résout le rôle admin depuis la base. Le fondateur est owner par défaut."""
    if not supabase:
        return None
    try:
        res = supabase.table("admin_roles").select("role").eq("user_id", user_id).limit(1).execute()
        if res.data:
            return res.data[0].get("role")
        # Filet de sécurité : le fondateur reste owner même si la ligne manque
        u = supabase.auth.admin.get_user_by_id(user_id)
        email = getattr(getattr(u, "user", None), "email", "") or ""
        if email.strip().lower() == FOUNDER_EMAIL:
            supabase.table("admin_roles").upsert(
                {"user_id": user_id, "role": "owner", "note": "Compte fondateur"}
            ).execute()
            return "owner"
    except Exception as e:
        logger.warning(f"get_admin_role failed: {e}")
    return None


def require_permission(permission: str):
    """Dépendance FastAPI : exige une permission précise."""
    def _dep(current_user: str = Depends(get_current_user)) -> Dict[str, Any]:
        role = get_admin_role(current_user)
        if not role or permission not in PERMISSIONS.get(role, set()):
            raise HTTPException(status_code=403, detail="Permission insuffisante.")
        return {"user_id": current_user, "role": role}
    return _dep


def _user_email(user_id: str) -> Optional[str]:
    try:
        u = supabase.auth.admin.get_user_by_id(user_id)
        return getattr(getattr(u, "user", None), "email", None)
    except Exception:
        return None


# ─────────────────────────────────────────────
# Identité & permissions de l'utilisateur courant
# ─────────────────────────────────────────────
@router.get("/me")
async def admin_me(current_user: str = Depends(get_current_user)):
    """Rôle et permissions du compte courant (pour l'affichage du back-office)."""
    role = get_admin_role(current_user)
    return {
        "is_admin": bool(role),
        "role": role,
        "role_label": ROLE_LABELS.get(role) if role else None,
        "permissions": sorted(PERMISSIONS.get(role, set())) if role else [],
    }


# ─────────────────────────────────────────────
# Vue d'ensemble
# ─────────────────────────────────────────────
@router.get("/stats")
async def admin_stats(ctx: Dict[str, Any] = Depends(require_permission("stats"))):
    """Indicateurs clés de la plateforme."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Service indisponible")

    def count(table: str, **filters) -> int:
        try:
            q = supabase.table(table).select("*", count="exact", head=True)
            for k, v in filters.items():
                q = q.eq(k, v)
            return q.execute().count or 0
        except Exception:
            return 0

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()

    try:
        tiers: Dict[str, int] = {}
        res = supabase.table("profiles").select("subscription_tier").execute()
        for row in res.data or []:
            tier = (row.get("subscription_tier") or "rookie").lower()
            tiers[tier] = tiers.get(tier, 0) + 1
    except Exception:
        tiers = {}

    def count_since(table: str, column: str, since: str) -> int:
        try:
            return supabase.table(table).select("*", count="exact", head=True).gte(column, since).execute().count or 0
        except Exception:
            return 0

    # Essais Paddock Pass actifs
    try:
        active_trials = supabase.table("profiles").select("*", count="exact", head=True) \
            .gt("trial_until", now.isoformat()).execute().count or 0
    except Exception:
        active_trials = 0

    return {
        "users": {
            "total": sum(tiers.values()),
            "by_tier": tiers,
            "paying": tiers.get("racer", 0) + tiers.get("team", 0),
        },
        "analyses": {
            "total": count("analyses"),
            "this_month": count_since("analyses", "created_at", month_start),
            "last_7_days": count_since("analyses", "created_at", week_ago),
        },
        "engagement": {
            "kart_profiles": count("kart_profiles"),
            "setups": count("kart_setups"),
            "tire_sets": count("kart_tire_sets"),
            "circuits": count("circuits"),
            "sessions_logged": count("kart_session_logs"),
        },
        "feedback": {
            "total": count("feedback_messages"),
            "new": count("feedback_messages", status="new"),
        },
        "paddock_pass": {
            "codes": count("promo_codes"),
            "redemptions": count("promo_redemptions"),
            "active_trials": active_trials,
        },
        "generated_at": now.isoformat(),
    }


# ─────────────────────────────────────────────
# Stats contextuelles (widget flottant selon la page)
# ─────────────────────────────────────────────
@router.get("/context-stats")
async def context_stats(path: str = "/", ctx: Dict[str, Any] = Depends(require_permission("stats"))):
    """Renvoie quelques indicateurs pertinents pour la page courante."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Service indisponible")

    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week = (now - timedelta(days=7)).isoformat()
    p = _normalize_path_light(path)

    def count_since(table: str, col: str, since: str, **eq) -> int:
        try:
            q = supabase.table(table).select("*", count="exact", head=True).gte(col, since)
            for k, v in eq.items():
                q = q.eq(k, v)
            return q.execute().count or 0
        except Exception:
            return 0

    def count(table: str) -> int:
        try:
            return supabase.table(table).select("*", count="exact", head=True).execute().count or 0
        except Exception:
            return 0

    # Vues + visiteurs uniques du jour (global, toujours affiché)
    views_today, unique_today = 0, 0
    try:
        res = supabase.table("page_events").select("session_id, path") \
            .eq("event_type", "view").gte("created_at", today).limit(5000).execute()
        rows = res.data or []
        views_today = len(rows)
        unique_today = len({r.get("session_id") for r in rows if r.get("session_id")})
        page_views_today = len([r for r in rows if r.get("path") == p])
    except Exception:
        page_views_today = 0

    stats: List[Dict[str, Any]] = [
        {"label": "Vues du site aujourd'hui", "value": views_today},
        {"label": "Visiteurs uniques aujourd'hui", "value": unique_today},
    ]
    title = "Aperçu du jour"

    # Indicateurs spécifiques à la page
    if p in ("/upload", "/analyser", "/analysis"):
        title = "Analyses"
        stats += [
            {"label": "Analyses aujourd'hui", "value": count_since("analyses", "created_at", today)},
            {"label": "Analyses cette semaine", "value": count_since("analyses", "created_at", week)},
        ]
    elif p == "/mon-kart":
        title = "Mon Kart"
        stats += [
            {"label": "Sessions importées (7j)", "value": count_since("kart_session_logs", "created_at", week)},
            {"label": "Garages configurés", "value": count("kart_profiles")},
        ]
    elif p == "/setup":
        title = "Réglages"
        stats += [
            {"label": "Réglages créés (7j)", "value": count_since("kart_setups", "created_at", week)},
            {"label": "Réglages au total", "value": count("kart_setups")},
        ]
    elif p == "/dashboard":
        title = "Tableau de bord"
        stats += [
            {"label": "Analyses au total", "value": count("analyses")},
            {"label": "Retours non traités", "value": count_since("feedback_messages", "created_at", "1970-01-01", status="new")},
        ]
    elif p == "/":
        title = "Accueil"
        stats += [
            {"label": "Vues de l'accueil aujourd'hui", "value": page_views_today},
            {"label": "Essais Paddock actifs", "value": _count_active_trials(now)},
        ]
    else:
        stats += [{"label": f"Vues de cette page aujourd'hui", "value": page_views_today}]

    return {"title": title, "path": p, "stats": stats, "generated_at": now.isoformat()}


def _normalize_path_light(path: str) -> str:
    p = (path or "/").split("?")[0].split("#")[0]
    p = re.sub(r"/[0-9a-fA-F-]{8,}", "", p)
    p = re.sub(r"/\d+", "", p)
    return p or "/"


def _count_active_trials(now: datetime) -> int:
    try:
        return supabase.table("profiles").select("*", count="exact", head=True) \
            .gt("trial_until", now.isoformat()).execute().count or 0
    except Exception:
        return 0


# ─────────────────────────────────────────────
# Gestion des rôles (owner uniquement)
# ─────────────────────────────────────────────
class RoleGrant(BaseModel):
    email: str
    role: str


@router.get("/roles")
async def list_roles(ctx: Dict[str, Any] = Depends(require_permission("roles"))):
    """Liste des collaborateurs et de leurs rôles."""
    try:
        res = supabase.table("admin_roles").select("*").order("created_at").execute()
        rows = res.data or []
        for r in rows:
            r["email"] = _user_email(r["user_id"])
            r["role_label"] = ROLE_LABELS.get(r.get("role"))
        return {"roles": rows, "available": [
            {"value": k, "label": v, "permissions": sorted(PERMISSIONS[k])} for k, v in ROLE_LABELS.items()
        ]}
    except Exception as e:
        logger.error(f"list_roles failed: {e}")
        raise HTTPException(status_code=500, detail="Lecture impossible.")


@router.post("/roles")
async def grant_role(payload: RoleGrant, ctx: Dict[str, Any] = Depends(require_permission("roles"))):
    """Attribuer un rôle à un collaborateur (par email)."""
    if payload.role not in PERMISSIONS:
        raise HTTPException(status_code=400, detail="Rôle inconnu.")
    email = payload.email.strip().lower()
    try:
        # Retrouve l'utilisateur par email (il doit déjà avoir un compte)
        users = supabase.auth.admin.list_users()
        target = next((u for u in users if (getattr(u, "email", "") or "").lower() == email), None)
        if not target:
            raise HTTPException(status_code=404, detail="Aucun compte ApexAI avec cet email.")
        supabase.table("admin_roles").upsert({
            "user_id": target.id,
            "role": payload.role,
            "granted_by": ctx["user_id"],
        }).execute()
        logger.info(f"role {payload.role} granted to {email} by {ctx['user_id']}")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"grant_role failed: {e}")
        raise HTTPException(status_code=500, detail="Attribution impossible.")


@router.delete("/roles/{user_id}")
async def revoke_role(user_id: str, ctx: Dict[str, Any] = Depends(require_permission("roles"))):
    """Révoquer l'accès d'un collaborateur."""
    if user_id == ctx["user_id"]:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas révoquer votre propre accès.")
    try:
        supabase.table("admin_roles").delete().eq("user_id", user_id).execute()
        return {"success": True}
    except Exception as e:
        logger.error(f"revoke_role failed: {e}")
        raise HTTPException(status_code=500, detail="Révocation impossible.")


# ─────────────────────────────────────────────
# Paddock Pass — gestion des codes
# ─────────────────────────────────────────────
class PromoCreate(BaseModel):
    label: Optional[str] = None
    tier: str = "racer"
    duration_hours: int = Field(default=24, alias="durationHours")
    max_redemptions: Optional[int] = Field(default=None, alias="maxRedemptions")
    expires_in_days: Optional[int] = Field(default=90, alias="expiresInDays")

    class Config:
        populate_by_name = True


def _generate_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    # Sans caractères ambigus (O/0, I/1) : ces codes sont lus sur un QR ou tapés au stand
    alphabet = "".join(c for c in alphabet if c not in "O0I1")
    return "PADDOCK-" + "".join(secrets.choice(alphabet) for _ in range(6))


@router.get("/promo-codes")
async def list_promo_codes(ctx: Dict[str, Any] = Depends(require_permission("promo"))):
    try:
        res = supabase.table("promo_codes").select("*").order("created_at", desc=True).limit(200).execute()
        return {"codes": res.data or []}
    except Exception as e:
        logger.error(f"list_promo_codes failed: {e}")
        raise HTTPException(status_code=500, detail="Lecture impossible.")


@router.post("/promo-codes")
async def create_promo_code(payload: PromoCreate, ctx: Dict[str, Any] = Depends(require_permission("promo"))):
    """Génère un Paddock Pass (code unique à distribuer sur les circuits)."""
    if payload.tier not in ("racer", "team"):
        raise HTTPException(status_code=400, detail="Offre inconnue.")
    if not (1 <= payload.duration_hours <= 720):
        raise HTTPException(status_code=400, detail="Durée invalide (1-720 h).")

    expires_at = None
    if payload.expires_in_days and payload.expires_in_days > 0:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)).isoformat()

    for _ in range(5):  # collision improbable, on retente par sécurité
        code = _generate_code()
        try:
            res = supabase.table("promo_codes").insert({
                "code": code,
                "label": payload.label,
                "tier": payload.tier,
                "duration_hours": payload.duration_hours,
                "max_redemptions": payload.max_redemptions,
                "expires_at": expires_at,
                "created_by": ctx["user_id"],
            }).execute()
            return {"success": True, "code": res.data[0] if res.data else {"code": code}}
        except Exception:
            continue
    raise HTTPException(status_code=500, detail="Génération impossible.")


@router.put("/promo-codes/{code}")
async def toggle_promo_code(code: str, active: bool,
                            ctx: Dict[str, Any] = Depends(require_permission("promo"))):
    """Activer / désactiver un code."""
    try:
        supabase.table("promo_codes").update({"active": active}).eq("code", code).execute()
        return {"success": True}
    except Exception as e:
        logger.error(f"toggle_promo_code failed: {e}")
        raise HTTPException(status_code=500, detail="Mise à jour impossible.")


@router.get("/promo-codes/{code}/redemptions")  # noqa: E302
async def code_redemptions(code: str, ctx: Dict[str, Any] = Depends(require_permission("promo"))):
    """Qui a activé ce code (suivi des conversions)."""
    try:
        res = supabase.table("promo_redemptions").select("*").eq("code", code) \
            .order("created_at", desc=True).limit(200).execute()
        rows = res.data or []
        for r in rows:
            r["email"] = _user_email(r["user_id"])
        return {"redemptions": rows}
    except Exception as e:
        logger.error(f"code_redemptions failed: {e}")
        raise HTTPException(status_code=500, detail="Lecture impossible.")
