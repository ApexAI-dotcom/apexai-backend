#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - User Profile API
Endpoints pour le profil utilisateur et l'abonnement (table profiles).
"""

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
import os
import logging

from supabase import create_client, Client

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialiser le client Supabase avec service_role
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_SERVICE_ROLE_KEY not in ("", "ton_service_role_key"):
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    logger.info("Supabase client initialized in user_routes: %s", SUPABASE_URL)
else:
    logger.warning(
        "Supabase client is None in user_routes - check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY"
    )


def _default_limits():
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


TIER_LIMITS = {
    "rookie": {
        "analyses_per_month": 3,
        "analyses_used": 0,
        "can_export_csv": False,
        "can_export_pdf": False,
        "can_compare": False,
        "max_members": 0,
        "max_circuits": 1,
        "max_cars": 1,
    },
    "racer": {
        "analyses_per_month": None,  # illimité
        "analyses_used": 0,
        "can_export_csv": True,
        "can_export_pdf": False,
        "can_compare": False,
        "max_members": 0,
        "max_circuits": None,
        "max_cars": None,
    },
    "team": {
        "analyses_per_month": None,
        "analyses_used": 0,
        "can_export_csv": True,
        "can_export_pdf": True,
        "can_compare": True,
        "max_members": 5,
        "max_circuits": None,
        "max_cars": None,
    },
}


@router.get("/api/user/subscription")
async def get_user_subscription(
    user_id: str = Query(..., description="User UUID from Supabase auth"),
    authorization: Optional[str] = Header(None),
):
    """
    Retourne l'abonnement actuel de l'utilisateur depuis la table profiles.
    Peut être appelé avec user_id en query OU avec Bearer JWT (user_id dérivé du token).
    """
    if not supabase:
        logger.warning("get_user_subscription: Supabase client not initialized")
        return {
            "tier": "rookie",
            "status": None,
            "billing_period": None,
            "subscription_end_date": None,
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "limits": _default_limits(),
        }

    # Si Bearer fourni, dériver user_id du JWT (priorité pour le frontend)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()
        try:
            user_response = supabase.auth.get_user(jwt=token)
            user = user_response.user if hasattr(user_response, "user") else user_response
            if user:
                uid = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
                if uid:
                    user_id = uid
        except Exception as e:
            logger.warning("get_user_subscription: JWT parse failed: %s", e)

    try:
        result = (
            supabase.table("profiles")
            .select(
                "subscription_tier, subscription_status, billing_period, "
                "stripe_customer_id, stripe_subscription_id, "
                "subscription_start_date, subscription_end_date, "
                "analyses_count_current_month, last_analysis_reset_date",
            )
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        if not result.data or len(result.data) == 0:
            return {
                "tier": "rookie",
                "status": None,
                "billing_period": None,
                "subscription_end_date": None,
                "stripe_customer_id": None,
                "stripe_subscription_id": None,
                "limits": _default_limits(),
            }

        data = result.data[0]
        tier = (data.get("subscription_tier") or "rookie").lower()
        if tier not in TIER_LIMITS:
            tier = "rookie"

        limits = {**TIER_LIMITS[tier]}
        if data.get("analyses_count_current_month") is not None:
            limits["analyses_used"] = int(data["analyses_count_current_month"])

        sub_end = data.get("subscription_end_date")
        subscription_end_date = sub_end.isoformat() if hasattr(sub_end, "isoformat") else str(sub_end) if sub_end else None

        logger.info(
            "get_user_subscription: user_id=%s tier=%s status=%s",
            user_id,
            tier,
            data.get("subscription_status"),
        )

        return {
            "tier": tier,
            "status": data.get("subscription_status"),
            "billing_period": data.get("billing_period"),
            "subscription_end_date": subscription_end_date,
            "stripe_customer_id": data.get("stripe_customer_id"),
            "stripe_subscription_id": data.get("stripe_subscription_id"),
            "limits": limits,
        }

    except Exception as e:
        logger.exception("get_user_subscription error for user_id=%s: %s", user_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/user/profile")
async def get_user_profile(authorization: Optional[str] = Header(None)):
    """
    Retourne le profil utilisateur (legacy: tier, analyses_count, trial_status).
    Nécessite Bearer token (JWT Supabase).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant")
    if not supabase:
        return JSONResponse(content={"tier": "free", "analyses_count": 0, "trial_status": "unknown"})

    token = authorization.replace("Bearer ", "").strip()
    try:
        user_response = supabase.auth.get_user(jwt=token)
        user = user_response.user if hasattr(user_response, "user") else user_response
        if not user:
            raise HTTPException(status_code=401, detail="Token invalide")
        user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="Token invalide")

        row = (
            supabase.table("profiles")
            .select("subscription_tier, analyses_count_current_month")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        tier = "free"
        analyses_count = 0
        if row.data and len(row.data) > 0:
            r = row.data[0]
            tier = "racer" if (r.get("subscription_tier") or "").lower() in ("racer", "team") else "free"
            analyses_count = int(r.get("analyses_count_current_month") or 0)

        email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
        return {"tier": tier, "analyses_count": analyses_count, "trial_status": "active", "email": email}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Profile error: %s", e)
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
