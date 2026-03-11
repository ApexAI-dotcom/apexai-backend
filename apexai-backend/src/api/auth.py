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
    secret = getattr(settings, "SUPABASE_JWT_SECRET", "") or ""
    # 1) Tentative decode JWT local (HS256)
    if secret:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")
            return str(user_id)
        except PyJWTError as e:
            token_preview = (token[:20] + "...") if len(token) > 20 else token
            logger.warning(
                "jwt_fail",
                extra={"error": str(e), "header": token_preview},
            )
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


# Router auth (endpoint debug temporaire)
from fastapi import APIRouter as _APIRouter

auth_router = _APIRouter(prefix="/api/auth", tags=["auth"])


@auth_router.get("/debug")
async def auth_debug(current_user: str = Depends(get_current_user)):
    """Temporaire : debug JWT → user_id + tier."""
    from ..core.subscription_service import get_subscription_tier
    tier = get_subscription_tier(current_user)
    return {"user_id": current_user, "tier": tier}
