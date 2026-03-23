#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Home Routes
GET /api/home/tips       — weekly rotating tips (public)
GET /api/home/insights   — personalized insights (JWT)
POST /api/home/insights/reset — reset objectives baseline (JWT)
"""

import datetime
import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from supabase import Client, create_client

from .auth import get_current_user
from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/home", tags=["home"])

# ---------------------------------------------------------------------------
# Supabase client (service role)
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL") or getattr(settings, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
)

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_SERVICE_ROLE_KEY not in ("", "ton_service_role_key"):
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    logger.info("Supabase client initialized in home_routes: %s", SUPABASE_URL)
else:
    logger.warning("Supabase client is None in home_routes — check env vars")

# ---------------------------------------------------------------------------
# Tips pool — rotated weekly (ISO week)
# ---------------------------------------------------------------------------
TIPS_POOL: List[Dict[str, str]] = [
    {
        "badge": "Nouveau",
        "badge_color": "blue",
        "title": "Optimise tes freinages",
        "body": "Un freinage progressif en 3 temps permet de gagner 0.3s par virage en moyenne.",
    },
    {
        "badge": "Populaire",
        "badge_color": "purple",
        "title": "Le regard en sortie",
        "body": "Regarde toujours la sortie du virage, pas l'apex. Ta trajectoire suivra ton regard.",
    },
    {
        "badge": "Astuce",
        "badge_color": "green",
        "title": "Trail braking",
        "body": "Relâche progressivement le frein en entrant dans le virage pour maintenir le grip avant et tourner plus vite.",
    },
    {
        "badge": "Pro",
        "badge_color": "orange",
        "title": "Accélère tôt en sortie",
        "body": "Commence à accélérer dès que tu redresses le volant. 0.1s de retard à l'accélération = 0.3s perdu en bout de ligne droite.",
    },
    {
        "badge": "Nouveau",
        "badge_color": "blue",
        "title": "Analyse tes données",
        "body": "Compare tes 3 dernières sessions pour identifier les virages où tu perds le plus de temps.",
    },
    {
        "badge": "Populaire",
        "badge_color": "purple",
        "title": "La régularité prime",
        "body": "Un pilote régulier à 0.2s du meilleur tour est plus rapide en course qu'un pilote irrégulier avec 1 tour rapide.",
    },
    {
        "badge": "Astuce",
        "badge_color": "green",
        "title": "Position assise optimale",
        "body": "Bras légèrement fléchis, dos collé au baquet. Une bonne position permet des gestes plus précis au volant.",
    },
    {
        "badge": "Pro",
        "badge_color": "orange",
        "title": "Gère tes pneus",
        "body": "Les 3 premiers tours servent à chauffer les pneus. Ne pousse pas à 100% avant le 4e tour.",
    },
]

DEFAULT_TIPS = TIPS_POOL[:2]


def _get_weekly_tips() -> List[Dict[str, str]]:
    """Return 2 tips based on the current ISO week number."""
    try:
        iso_week = datetime.date.today().isocalendar()[1]
        pool_size = len(TIPS_POOL)
        idx = (iso_week * 2) % pool_size
        tip1 = TIPS_POOL[idx]
        tip2 = TIPS_POOL[(idx + 1) % pool_size]
        return [tip1, tip2]
    except Exception:
        return DEFAULT_TIPS


# ---------------------------------------------------------------------------
# Insights cache — per-user, 60s TTL
# ---------------------------------------------------------------------------
_insights_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 60  # seconds


def _cache_get(user_id: str) -> Optional[Dict[str, Any]]:
    entry = _insights_cache.get(user_id)
    if entry and (time.time() - entry["_ts"]) < _CACHE_TTL:
        return entry
    return None


def _cache_set(user_id: str, data: Dict[str, Any]) -> None:
    _insights_cache[user_id] = {**data, "_ts": time.time()}


def _cache_invalidate(user_id: str) -> None:
    _insights_cache.pop(user_id, None)


# ---------------------------------------------------------------------------
# Weak-point label mapping
# ---------------------------------------------------------------------------
CATEGORY_LABELS = {
    "apex_precision": "Précision d'apex",
    "trajectory_consistency": "Régularité trajectoire",
    "apex_speed": "Vitesse en virage",
    "sector_times": "Temps secteurs",
}

_migration_warning_logged = False


def _log_migration_warning_once():
    global _migration_warning_logged
    if not _migration_warning_logged:
        logger.warning(
            "home_routes: baseline columns not found in profiles table. "
            "Run ALTER TABLE profiles ADD COLUMN IF NOT EXISTS baseline_score real; "
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS baseline_time real; "
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS objectives_reset_at timestamptz;"
        )
        _migration_warning_logged = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/tips")
async def get_tips():
    """Weekly rotating driving tips (public, no auth)."""
    iso_week = datetime.date.today().isocalendar()[1]
    return {"week": iso_week, "tips": _get_weekly_tips()}


@router.get("/insights")
async def get_insights(
    request: Request,
    current_user: str = Depends(get_current_user),
):
    """Personalized homepage insights (JWT required)."""
    # Check cache
    cached = _cache_get(current_user)
    if cached:
        payload = {k: v for k, v in cached.items() if k != "_ts"}
        return JSONResponse(content=payload)

    if not supabase:
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")

    try:
        # 1. Fetch last 10 analyses (perf-limited)
        result = (
            supabase.table("analyses")
            .select(
                "id, created_at, score, lap_time, corner_analysis, performance_score"
            )
            .eq("user_id", current_user)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        analyses = list(result.data) if result.data else []

        # 2. Fetch baseline from profiles (graceful if columns missing)
        baseline_score = None
        baseline_time = None
        reset_at = None
        try:
            profile_r = (
                supabase.table("profiles")
                .select("baseline_score, baseline_time, objectives_reset_at")
                .eq("id", current_user)
                .limit(1)
                .execute()
            )
            if profile_r.data and len(profile_r.data) > 0:
                p = profile_r.data[0]
                baseline_score = p.get("baseline_score")
                baseline_time = p.get("baseline_time")
                raw_reset = p.get("objectives_reset_at")
                if raw_reset:
                    reset_at = str(raw_reset)
        except Exception as e:
            # Columns probably don't exist yet
            _log_migration_warning_once()
            logger.debug("home_routes: profile baseline fetch failed: %s", e)

        # Insufficient data
        if len(analyses) < 2:
            payload = {
                "insufficient_data": True,
                "time_gained": None,
                "weak_point": None,
                "best_score": analyses[0]["score"] if analyses else 0,
                "best_lap_time": analyses[0]["lap_time"] if analyses else 0,
                "analyses_count": len(analyses),
                "baseline_score": baseline_score,
                "baseline_time": baseline_time,
                "reset_at": reset_at,
            }
            _cache_set(current_user, payload)
            return JSONResponse(content=payload)

        # 3. Compute best score / best lap_time
        scores = [a["score"] for a in analyses if a.get("score") is not None]
        lap_times = [a["lap_time"] for a in analyses if a.get("lap_time") and a["lap_time"] > 0]
        best_score = max(scores) if scores else 0
        best_lap_time = min(lap_times) if lap_times else 0

        # 4. Time gained (smoothed)
        time_gained = _compute_time_gained(analyses, baseline_time)

        # 5. Weak point
        weak_point = _compute_weak_point(analyses)

        payload = {
            "insufficient_data": False,
            "time_gained": time_gained,
            "weak_point": weak_point,
            "best_score": best_score,
            "best_lap_time": round(best_lap_time, 2) if best_lap_time else 0,
            "analyses_count": len(analyses),
            "baseline_score": baseline_score,
            "baseline_time": baseline_time,
            "reset_at": reset_at,
        }
        _cache_set(current_user, payload)
        return JSONResponse(content=payload)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_insights error for user_id=%s: %s", current_user, e)
        raise HTTPException(status_code=500, detail="Erreur lors du calcul des insights")


@router.post("/insights/reset")
async def reset_insights(
    request: Request,
    current_user: str = Depends(get_current_user),
):
    """Reset objectives baseline (JWT required). Acts only on authenticated user."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")

    try:
        # Fetch current bests
        result = (
            supabase.table("analyses")
            .select("score, lap_time")
            .eq("user_id", current_user)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        analyses = list(result.data) if result.data else []

        scores = [a["score"] for a in analyses if a.get("score") is not None]
        lap_times = [a["lap_time"] for a in analyses if a.get("lap_time") and a["lap_time"] > 0]
        current_best_score = max(scores) if scores else None
        current_best_time = min(lap_times) if lap_times else None

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        try:
            supabase.table("profiles").update({
                "baseline_score": current_best_score,
                "baseline_time": current_best_time,
                "objectives_reset_at": now,
            }).eq("id", current_user).execute()
        except Exception as e:
            _log_migration_warning_once()
            logger.error("reset_insights: update profiles failed: %s", e)
            raise HTTPException(
                status_code=500,
                detail="Impossible de réinitialiser les objectifs. Les colonnes de migration sont peut-être manquantes.",
            )

        # Invalidate cache
        _cache_invalidate(current_user)

        logger.info(
            "objectives_reset",
            extra={
                "user_id": current_user,
                "baseline_score": current_best_score,
                "baseline_time": current_best_time,
            },
        )

        return {
            "success": True,
            "baseline_score": current_best_score,
            "baseline_time": current_best_time,
            "reset_at": now,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("reset_insights error for user_id=%s: %s", current_user, e)
        raise HTTPException(status_code=500, detail="Erreur lors de la réinitialisation")


# ---------------------------------------------------------------------------
# Internal helpers — no changes to analysis/scoring/coaching
# ---------------------------------------------------------------------------


def _compute_time_gained(
    analyses: List[Dict[str, Any]],
    baseline_time: Optional[float],
) -> Optional[float]:
    """
    Compute time gained in seconds.
    1. If baseline_time exists (from reset) → baseline_time − current best lap_time
    2. Else → smoothed: avg of 3 best recent vs avg of 3 oldest in window
    3. Clamp [-30, +30], round 1 decimal
    """
    lap_times = [a["lap_time"] for a in analyses if a.get("lap_time") and a["lap_time"] > 0]
    if len(lap_times) < 2:
        return None

    current_best = min(lap_times)

    if baseline_time is not None and baseline_time > 0:
        raw = baseline_time - current_best
    else:
        # Smoothed: analyses are sorted desc (newest first)
        # "recent" = first half, "oldest" = second half
        half = max(1, len(lap_times) // 2)
        recent = sorted(lap_times[:half])[:3]   # 3 best of recent
        oldest = sorted(lap_times[half:])[:3]    # 3 best of oldest
        if not recent or not oldest:
            return None
        avg_recent = sum(recent) / len(recent)
        avg_oldest = sum(oldest) / len(oldest)
        raw = avg_oldest - avg_recent  # positive = improvement

    # Clamp and round
    clamped = max(-30.0, min(30.0, raw))
    return round(clamped, 1)


def _compute_weak_point(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Identify weakest area.
    1. Primary: aggregate corner_analysis → top 3 lowest-scoring recurring corner IDs
    2. Fallback: performance_score.breakdown → weakest category
    """
    # Try corner_analysis first
    corner_scores: Dict[int, List[float]] = {}
    for a in analyses:
        ca = a.get("corner_analysis")
        if not ca or not isinstance(ca, list):
            continue
        for corner in ca:
            if not isinstance(corner, dict):
                continue
            cid = corner.get("corner_id") or corner.get("corner_number")
            score = corner.get("score")
            if cid is not None and score is not None:
                corner_scores.setdefault(int(cid), []).append(float(score))

    if corner_scores:
        # Average score per corner, then find worst 3
        avg_scores = {cid: sum(s) / len(s) for cid, s in corner_scores.items()}
        worst = sorted(avg_scores.items(), key=lambda x: x[1])[:3]
        worst_ids = [cid for cid, _ in worst]
        avg_worst = sum(s for _, s in worst) / len(worst) if worst else 50

        # Label based on average worst score
        if avg_worst < 50:
            label = "Virages lents"
        elif avg_worst < 65:
            label = "Trajectoire à améliorer"
        else:
            label = "Virages à peaufiner"

        return {"label": label, "corners": worst_ids}

    # Fallback: performance_score.breakdown
    breakdown_totals: Dict[str, List[float]] = {}
    for a in analyses:
        ps = a.get("performance_score")
        if not ps or not isinstance(ps, dict):
            continue
        bd = ps.get("breakdown")
        if not bd or not isinstance(bd, dict):
            continue
        for key in ("apex_precision", "trajectory_consistency", "apex_speed", "sector_times"):
            val = bd.get(key)
            if val is not None:
                breakdown_totals.setdefault(key, []).append(float(val))

    if breakdown_totals:
        avg_bd = {k: sum(v) / len(v) for k, v in breakdown_totals.items()}
        weakest_key = min(avg_bd, key=avg_bd.get)  # type: ignore[arg-type]
        label = CATEGORY_LABELS.get(weakest_key, "Point faible")
        return {"label": label, "corners": []}

    return {"label": "Données insuffisantes", "corners": []}
