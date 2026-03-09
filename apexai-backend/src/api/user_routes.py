#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - User Profile API
Endpoints pour le profil utilisateur et l'abonnement (table profiles).
Auth : JWT Bearer obligatoire via get_current_user (SEC-001).
"""

import json
import logging
import os
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from jwt import PyJWTError
from supabase import Client, create_client

from .auth import get_current_user
from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL") or getattr(settings, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
)
JWT_SECRET = getattr(settings, "SUPABASE_JWT_SECRET", "") or os.getenv("SUPABASE_JWT_SECRET", "")

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
        "analyses_per_month": None,
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


def _log_subscription_request(user_id: str, source: str, result: str, error: Optional[str] = None):
    log_obj = {
        "step": "subscription_request",
        "user_id": user_id,
        "source": source,
        "result": result,
    }
    if error:
        log_obj["error"] = error
    logger.info("subscription_request %s", json.dumps(log_obj))


@router.get("/api/user/subscription")
async def get_user_subscription(
    request: Request,
    current_user: str = Depends(get_current_user),
):
    """
    Retourne l'abonnement depuis la table profiles. Auth JWT obligatoire.
    """
    logger.info(
        "user_action",
        extra={
            "action": "subscription",
            "user_id": current_user,
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    )
    if not supabase:
        _log_subscription_request(current_user, "jwt", "error", "Supabase client not initialized")
        raise HTTPException(
            status_code=503,
            detail="Service temporairement indisponible",
        )

    try:
        result = (
            supabase.table("profiles")
            .select(
                "subscription_tier, subscription_status, billing_period, "
                "stripe_customer_id, stripe_subscription_id, "
                "subscription_start_date, subscription_end_date, "
                "analyses_count_current_month, last_analysis_reset_date",
            )
            .eq("id", current_user)
            .limit(1)
            .execute()
        )

        if not result.data or len(result.data) == 0:
            _log_subscription_request(current_user, "jwt", "not_found")
            raise HTTPException(status_code=404, detail="Profil non trouvé")

        data = result.data[0]
        tier = (data.get("subscription_tier") or "rookie").lower()
        if tier not in TIER_LIMITS:
            tier = "rookie"

        limits = {**TIER_LIMITS[tier]}
        if data.get("analyses_count_current_month") is not None:
            limits["analyses_used"] = int(data["analyses_count_current_month"])

        sub_start = data.get("subscription_start_date")
        subscription_start_date = (
            sub_start.isoformat() if hasattr(sub_start, "isoformat") else str(sub_start) if sub_start else None
        )
        sub_end = data.get("subscription_end_date")
        subscription_end_date = (
            sub_end.isoformat() if hasattr(sub_end, "isoformat") else str(sub_end) if sub_end else None
        )
        analyses_limit = 3 if tier == "rookie" else None

        _log_subscription_request(current_user, "jwt", tier)

        return {
            "tier": tier,
            "status": data.get("subscription_status"),
            "billing_period": data.get("billing_period"),
            "subscription_start_date": subscription_start_date,
            "subscription_end_date": subscription_end_date,
            "analyses_count_current_month": data.get("analyses_count_current_month"),
            "analyses_limit": analyses_limit,
            "stripe_customer_id": data.get("stripe_customer_id"),
            "stripe_subscription_id": data.get("stripe_subscription_id"),
            "limits": limits,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_user_subscription error for user_id=%s: %s", current_user, e)
        _log_subscription_request(current_user, "jwt", "error", str(e))
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
        if JWT_SECRET:
            payload = jwt.decode(
                token,
                JWT_SECRET,
                audience="authenticated",
                algorithms=["HS256"],
            )
            user_id = payload.get("sub")
        else:
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
            .eq("id", current_user)
            .limit(1)
            .execute()
        )
        tier = "free"
        analyses_count = 0
        if row.data and len(row.data) > 0:
            r = row.data[0]
            tier = "racer" if (r.get("subscription_tier") or "").lower() in ("racer", "team") else "free"
            analyses_count = int(r.get("analyses_count_current_month") or 0)

        if JWT_SECRET:
            email = payload.get("email")
        else:
            user = user_response.user if hasattr(user_response, "user") else user_response
            email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
        return {"tier": tier, "analyses_count": analyses_count, "trial_status": "active", "email": email}
    except HTTPException:
        raise
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
    except Exception as e:
        logger.warning("Profile error: %s", e)
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
