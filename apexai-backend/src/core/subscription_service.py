#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Service abonnements et limites par tier
Vérification des limites (analyses, export, comparaison) et mise à jour du compteur.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Configuration Supabase (service_role pour bypass RLS)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

_supabase_client: Optional[Any] = None


def _get_supabase():
    """Retourne le client Supabase (créé une fois)."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_KEY == "ton_service_role_key":
        return None
    try:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return _supabase_client
    except ImportError:
        logger.warning("supabase package not installed, subscription limits disabled")
        return None
    except Exception as e:
        logger.warning("Could not create Supabase client for subscription_service: %s", e)
        return None


# -----------------------------------------------------------------------------
# Limites par plan (rookie / racer / team)
# -----------------------------------------------------------------------------
# analyses_per_month: -1 = illimité
# max_circuits, max_cars: -1 = illimité
# export_csv, export_pdf, comparison: bool
# max_members: 0 = non applicable, 5 = team (comparaison 5 pilotes)
TIER_LIMITS = {
    "rookie": {
        "analyses_per_month": 3,
        "max_circuits": 1,
        "max_cars": 1,
        "export_csv": False,
        "export_pdf": False,
        "comparison": False,
        "max_members": 0,
    },
    "racer": {
        "analyses_per_month": -1,
        "max_circuits": -1,
        "max_cars": -1,
        "export_csv": True,
        "export_pdf": False,
        "comparison": False,
        "max_members": 0,
    },
    "team": {
        "analyses_per_month": -1,
        "max_circuits": -1,
        "max_cars": -1,
        "export_csv": True,
        "export_pdf": True,
        "comparison": True,
        "max_members": 5,
    },
}


def _parse_tier(tier: Optional[str]) -> str:
    """Retourne un tier valide (rookie par défaut)."""
    if tier and tier.lower() in TIER_LIMITS:
        return tier.lower()
    return "rookie"


def _fetch_profile(user_id: str) -> Optional[dict[str, Any]]:
    """Récupère le profil (subscription_tier, analyses_count_current_month, last_analysis_reset_date)."""
    supabase = _get_supabase()
    if not supabase:
        return None
    try:
        result = (
            supabase.table("profiles")
            .select(
                "subscription_tier",
                "analyses_count_current_month",
                "last_analysis_reset_date",
            )
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return dict(result.data[0])
        return None
    except Exception as e:
        logger.exception("subscription_service: fetch_profile failed for user %s: %s", user_id, e)
        return None


def _reset_monthly_count(user_id: str) -> bool:
    """Remet le compteur mensuel à 0 et met à jour last_analysis_reset_date. Retourne True si OK."""
    supabase = _get_supabase()
    if not supabase:
        return False
    try:
        now_utc = datetime.now(timezone.utc).isoformat()
        supabase.table("profiles").update({
            "analyses_count_current_month": 0,
            "last_analysis_reset_date": now_utc,
        }).eq("id", user_id).execute()
        logger.info("subscription_service: reset monthly count for user %s", user_id)
        return True
    except Exception as e:
        logger.exception("subscription_service: reset_monthly_count failed for user %s: %s", user_id, e)
        return False


def _parse_reset_date(value: Any) -> Optional[datetime]:
    """Parse last_analysis_reset_date (ISO string ou datetime) en datetime timezone-aware."""
    if value is None:
        return None
    if hasattr(value, "year"):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    try:
        s = str(value).strip()
        if not s:
            return None
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def check_analysis_limit(user_id: str) -> bool:
    """
    Vérifie si l'utilisateur peut lancer une analyse.
    Reset automatique du compteur mensuel si on a changé de mois (UTC).
    Retourne True si autorisé, False si limite atteinte ou erreur (on refuse par défaut).
    """
    profile = _fetch_profile(user_id)
    if not profile:
        # Pas de profil ou Supabase indispo : on applique rookie
        limits = TIER_LIMITS["rookie"]
        logger.warning("subscription_service: no profile for user %s, applying rookie limit", user_id)
        return limits["analyses_per_month"] != 0  # rookie = 3, donc True

    tier = _parse_tier(profile.get("subscription_tier"))
    limits = TIER_LIMITS[tier]
    if limits["analyses_per_month"] == -1:
        return True

    count = profile.get("analyses_count_current_month")
    if count is None:
        count = 0
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 0

    last_reset = _parse_reset_date(profile.get("last_analysis_reset_date"))
    now = datetime.now(timezone.utc)
    if last_reset:
        if last_reset.month != now.month or last_reset.year != now.year:
            _reset_monthly_count(user_id)
            count = 0
    # Si pas de last_reset, on considère le mois courant et on ne reset pas ici (éviter écriture inutile)

    if count >= limits["analyses_per_month"]:
        logger.info(
            "subscription_service: analysis limit reached for user %s (tier=%s, count=%s, limit=%s)",
            user_id, tier, count, limits["analyses_per_month"],
        )
        return False
    return True


def increment_analysis_count(user_id: str) -> None:
    """Incrémente le compteur d'analyses du mois après une analyse réussie."""
    supabase = _get_supabase()
    if not supabase:
        logger.warning("subscription_service: Supabase not available, cannot increment count for %s", user_id)
        return
    try:
        profile = _fetch_profile(user_id)
        if not profile:
            # Insérer ou ignorer : le profil peut ne pas exister si trigger pas encore passé
            logger.warning("subscription_service: no profile for user %s, skip increment", user_id)
            return
        count = profile.get("analyses_count_current_month", 0)
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 0
        new_count = count + 1
        supabase.table("profiles").update({
            "analyses_count_current_month": new_count,
        }).eq("id", user_id).execute()
        logger.info("subscription_service: incremented analysis count for user %s -> %s", user_id, new_count)
    except Exception as e:
        logger.exception("subscription_service: increment_analysis_count failed for user %s: %s", user_id, e)


def can_export(user_id: str, format: str) -> bool:
    """Vérifie si l'utilisateur peut exporter. format: 'csv' | 'pdf'. CSV pour racer+, PDF pour team uniquement."""
    profile = _fetch_profile(user_id)
    tier = _parse_tier(profile.get("subscription_tier") if profile else None)
    limits = TIER_LIMITS[tier]
    fmt = (format or "").strip().lower()
    if fmt == "csv":
        return bool(limits["export_csv"])
    if fmt == "pdf":
        return bool(limits["export_pdf"])
    return False


def can_compare(user_id: str) -> bool:
    """Vérifie si la comparaison pilotes est autorisée (team uniquement)."""
    profile = _fetch_profile(user_id)
    tier = _parse_tier(profile.get("subscription_tier") if profile else None)
    return bool(TIER_LIMITS[tier]["comparison"])


def get_user_limits(user_id: str) -> dict[str, Any]:
    """
    Retourne les limites et l'usage actuel pour affichage frontend.
    Clés: tier, analyses_per_month (limit), analyses_used, can_export_csv, can_export_pdf, can_compare, max_members.
    """
    profile = _fetch_profile(user_id)
    tier = _parse_tier(profile.get("subscription_tier") if profile else None)
    limits = TIER_LIMITS[tier].copy()

    analyses_used = 0
    if profile is not None:
        last_reset = _parse_reset_date(profile.get("last_analysis_reset_date"))
        now = datetime.now(timezone.utc)
        if last_reset and last_reset.month == now.month and last_reset.year == now.year:
            try:
                analyses_used = int(profile.get("analyses_count_current_month", 0))
            except (TypeError, ValueError):
                pass

    analyses_limit = limits["analyses_per_month"]
    if analyses_limit == -1:
        analyses_limit = None  # illimité pour l'affichage

    return {
        "tier": tier,
        "analyses_per_month": analyses_limit,
        "analyses_used": analyses_used,
        "can_export_csv": limits["export_csv"],
        "can_export_pdf": limits["export_pdf"],
        "can_compare": limits["comparison"],
        "max_members": limits["max_members"],
        "max_circuits": limits["max_circuits"] if limits["max_circuits"] != -1 else None,
        "max_cars": limits["max_cars"] if limits["max_cars"] != -1 else None,
    }
