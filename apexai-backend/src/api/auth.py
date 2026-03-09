#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Auth JWT centralisée (SEC-001).
Dépendance get_current_user pour routes protégées Stripe / user.
"""

import logging

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError

from .config import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=True)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    Vérifie le JWT Supabase et retourne le user_id (sub).
    Sans SUPABASE_JWT_SECRET → 501.
    """
    secret = getattr(settings, "SUPABASE_JWT_SECRET", "") or ""
    if not secret:
        logger.warning("SUPABASE_JWT_SECRET not set, JWT auth unavailable")
        raise HTTPException(status_code=501, detail="Auth not configured")

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
        logger.warning("JWT decode failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid/expired token")
