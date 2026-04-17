#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Auth JWT centralisée (SEC-001).
Dépendance get_current_user pour routes protégées Stripe / user.
Fallback Supabase auth.get_user() si decode JWT échoue (support access_token, alg non strict).
"""

import logging
import os
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError

from .config import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=True)

# Client Supabase pour fallback get_user (pas strict JWT alg)
_supabase_auth_client = None


def _get_supabase_auth():
    """Client Supabase pour auth.get_user(jwt=token) en fallback."""
    global _supabase_auth_client
    if _supabase_auth_client is not None:
        return _supabase_auth_client
    url = os.getenv("SUPABASE_URL") or getattr(settings, "SUPABASE_URL", "")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
    )
    if not url or not key or key == "ton_service_role_key":
        return None
    try:
        from supabase import create_client
        _supabase_auth_client = create_client(url, key)  # noqa: PLW0603
        return _supabase_auth_client
    except Exception as e:
        logger.warning("auth: could not create Supabase client for fallback: %s", e)
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    Vérifie le JWT Supabase et retourne le user_id (sub).
    Fallback : supabase.auth.get_user(token) si decode JWT échoue (support access_token, alg non strict).
    """
    supabase_url = getattr(settings, "SUPABASE_URL", "")
    secret = getattr(settings, "SUPABASE_JWT_SECRET", "") or ""
    # 1) Tentative decode JWT local (HS256 uniquement)
    if secret:
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
            user_id = payload.get("sub")
            if user_id:
                return str(user_id)
        except Exception:
            pass

    # 2) Fallback via Supabase API (plus lent mais fiable)
    if not supabase_url:
        return None
    try:
        from supabase import create_client
        service_key = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
        if not service_key: return None
        client = create_client(supabase_url, service_key)
        user_response = client.auth.get_user(jwt=token)
        user = user_response.user if hasattr(user_response, "user") else user_response
        return user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    except Exception:
        return None
    else:
        logger.warning("SUPABASE_JWT_SECRET not set, trying Supabase auth fallback only")

    # 2) Fallback : Supabase auth.get_user (support access_token, pas strict JWT alg)
    supabase = _get_supabase_auth()
    if supabase:
        try:
            user_response = supabase.auth.get_user(jwt=token)
            user = user_response.user if hasattr(user_response, "user") else user_response
            if user and getattr(user, "id", None):
                return str(user.id)
            if isinstance(user, dict) and user.get("id"):
                return str(user["id"])
        except Exception as e:
            logger.warning("auth fallback get_user failed: %s", e)

    raise HTTPException(status_code=401, detail="Invalid/expired token")


# Router auth (debug + on-login)
from fastapi import APIRouter as _APIRouter, Request

auth_router = _APIRouter(prefix="/api/auth", tags=["auth"])

# Noms des pistes utilisées pour les données de test (on-login)
_TEST_TRACK_NAMES = ("Monaco Kart", "Monza Kart", "Local Kart")


@auth_router.get("/debug")
async def auth_debug(current_user: str = Depends(get_current_user)):
    """Temporaire : debug JWT → user_id + tier."""
    from ..core.subscription_service import get_subscription_tier
    tier = get_subscription_tier(current_user)
    return {"user_id": current_user, "tier": tier}


@auth_router.post("/on-login")
async def on_login(request: Request, current_user: str = Depends(get_current_user)):
    """
    Appelé après login frontend : supprime les anciennes analyses test puis insère 3 nouvelles
    (Monaco Kart, Monza Kart, Local Kart) pour current_user.
    """
    supabase = _get_supabase_auth()
    if not supabase:
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")
    try:
        supabase.table("analyses").delete().eq("user_id", current_user).in_(
            "track_name", list(_TEST_TRACK_NAMES)
        ).execute()
        supabase.table("analyses").insert([
            {
                "user_id": current_user,
                "track_name": "Monaco Kart",
                "lap_count": 12,
                "ai_insights": {"braking_score": 85, "lap_improvement": "+0.3s"},
            },
            {
                "user_id": current_user,
                "track_name": "Monza Kart",
                "lap_count": 15,
                "ai_insights": {"braking_score": 92, "lap_improvement": "+0.1s"},
            },
            {
                "user_id": current_user,
                "track_name": "Local Kart",
                "lap_count": 8,
                "ai_insights": {"braking_score": 78, "lap_improvement": "-0.2s"},
            },
        ]).execute()
        logger.info(
            "auto_test_data_created",
            extra={"user_id": current_user, "ip": request.client.host if request.client else None},
        )
        return {"inserted": 3}
    except Exception as e:
        logger.exception("on_login failed for user_id=%s: %s", current_user, e)
        raise HTTPException(status_code=500, detail="Erreur on-login")
