#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - User Profile API
Endpoint pour le profil utilisateur (tier, analyses_count, trial_status)
"""

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["user"])

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

supabase_client = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY and SUPABASE_SERVICE_KEY != "ton_service_role_key":
    try:
        from supabase import create_client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    except ImportError:
        pass


@router.get("/profile")
async def get_user_profile(authorization: Optional[str] = Header(None)):
    """
    Retourne le profil utilisateur : tier, analyses_count, trial_status.
    Nécessite Bearer token (JWT Supabase) dans Authorization.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant")

    token = authorization.replace("Bearer ", "").strip()
    if not supabase_client:
        return JSONResponse(content={
            "tier": "free",
            "analyses_count": 0,
            "trial_status": "unknown",
        })

    try:
        user_response = supabase_client.auth.get_user(jwt=token)
        user = user_response.user if hasattr(user_response, "user") else user_response
        if not user:
            raise HTTPException(status_code=401, detail="Token invalide")

        meta = user.get("user_metadata", {}) or {}
        sub = meta.get("subscription", {})
        tier = meta.get("tier", sub.get("plan", "free"))
        trial_end = meta.get("trial_end") or sub.get("trial_end")

        trial_status = "active"
        if trial_end:
            import time
            if time.time() > trial_end:
                trial_status = "expired"
            else:
                trial_status = "trial"

        # analyses_count : depuis une table ou metadata (à implémenter selon BDD)
        analyses_count = meta.get("analyses_count", 0)

        email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
        return {
            "tier": tier,
            "analyses_count": analyses_count,
            "trial_status": trial_status,
            "email": email,
        }
    except Exception as e:
        logger.warning(f"Profile error: {e}")
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")


@router.get("/subscription")
async def get_user_subscription(authorization: Optional[str] = Header(None)):
    """
    Retourne le tier, statut et limites d'abonnement depuis la table profiles.
    Nécessite Bearer token (JWT Supabase).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant")

    token = authorization.replace("Bearer ", "").strip()
    if not supabase_client:
        return {
            "tier": "rookie",
            "status": None,
            "billing_period": None,
            "subscription_end_date": None,
            "limits": _default_limits(),
        }

    try:
        user_response = supabase_client.auth.get_user(jwt=token)
        user = user_response.user if hasattr(user_response, "user") else user_response
        if not user:
            raise HTTPException(status_code=401, detail="Token invalide")

        user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="Token invalide")

        try:
            from src.core.subscription_service import get_user_limits
            limits = get_user_limits(user_id)
            tier = limits.get("tier", "rookie")
            # Récupérer subscription_status, billing_period, subscription_end_date depuis profiles
            result = supabase_client.table("profiles").select(
                "subscription_status", "billing_period", "subscription_end_date"
            ).eq("id", user_id).limit(1).execute()
            status = None
            billing_period = None
            subscription_end_date = None
            if result.data and len(result.data) > 0:
                row = result.data[0]
                status = row.get("subscription_status")
                billing_period = row.get("billing_period")
                subscription_end_date = row.get("subscription_end_date")
            return {
                "tier": tier,
                "status": status,
                "billing_period": billing_period,
                "subscription_end_date": subscription_end_date,
                "limits": limits,
            }
        except Exception as e:
            logger.warning(f"get_user_subscription: {e}")
            return {
                "tier": "rookie",
                "status": None,
                "billing_period": None,
                "subscription_end_date": None,
                "limits": _default_limits(),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Subscription error: {e}")
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")


def _default_limits():
    """Limites par défaut (rookie) quand Supabase/subscription_service indisponible."""
    return {
        "tier": "rookie",
        "analyses_per_month": 3,
        "analyses_used": 0,
        "can_export_csv": False,
        "can_export_pdf": False,
        "can_compare": False,
        "max_members": 0,
        "max_circuits": 1,
        "max_cars": 1,
    }
