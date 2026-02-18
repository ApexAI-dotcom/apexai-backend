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

        email = user_dict.get("email") or getattr(user, "email", None)
        return {
            "tier": tier,
            "analyses_count": analyses_count,
            "trial_status": trial_status,
            "email": email,
        }
    except Exception as e:
        logger.warning(f"Profile error: {e}")
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
