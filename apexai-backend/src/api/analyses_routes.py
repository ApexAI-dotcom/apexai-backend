#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API Analyses (paginated, JWT + RLS)
GET /api/analyses : liste paginée des analyses de l'utilisateur connecté.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from supabase import Client, create_client

from .auth import get_current_user
from .config import settings
from ..core.subscription_service import get_subscription_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analyses"])

SUPABASE_URL = os.getenv("SUPABASE_URL") or getattr(settings, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
)

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_SERVICE_ROLE_KEY not in ("", "ton_service_role_key"):
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    logger.info("Supabase client initialized in analyses_routes: %s", SUPABASE_URL)
else:
    logger.warning("Supabase client is None in analyses_routes - check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")


@router.get("/analyses")
async def get_analyses(
    request: Request,
    current_user: str = Depends(get_current_user),
    page: int = 1,
    limit: int = 20,
    user_id: Optional[str] = Query(None, include_in_schema=False),
) -> JSONResponse:
    """
    Liste paginée des analyses de l'utilisateur (JWT obligatoire).
    RLS : seules les lignes user_id = current_user sont visibles.
    Le query ?user_id= est ignoré (toujours current_user du JWT).
    """
    if user_id is not None and user_id.strip():
        logger.warning(
            "analyses_list: query user_id ignored (use JWT)",
            extra={"user_id": current_user, "query_user_id": user_id},
        )
    if not supabase:
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")

    tier = get_subscription_tier(current_user)

    if page < 1:
        page = 1
    if limit < 1:
        limit = 20
    if limit > 100:
        limit = 100

    start = (page - 1) * limit
    end = page * limit - 1

    try:
        # Données paginées
        r = (
            supabase.table("analyses")
            .select("*")
            .eq("user_id", current_user)
            .order("created_at", desc=True)
            .range(start, end)
            .execute()
        )
        analyses = list(r.data) if r.data else []

        # Total pour la pagination
        count_r = (
            supabase.table("analyses")
            .select("id")
            .eq("user_id", current_user)
            .execute()
        )
        total_count = len(count_r.data) if count_r.data else 0

        logger.info(
            "analyses_list",
            extra={
                "user_id": current_user,
                "ip": request.client.host if request.client else None,
                "page": page,
                "count": len(analyses),
                "tier": tier,
            },
        )

        return JSONResponse(
            content={
                "analyses": analyses,
                "page": page,
                "limit": limit,
                "total": total_count,
            }
        )
    except Exception as e:
        logger.exception("get_analyses failed for user_id=%s: %s", current_user, e)
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des analyses")


@router.post("/analyses/test-data")
async def create_test_data(
    request: Request,
    current_user: str = Depends(get_current_user),
) -> JSONResponse:
    """
    TEMPORAIRE. Insère 3 analyses de test pour current_user.
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")

    fake_analyses = [
        {
            "user_id": current_user,
            "track_name": "Circuit Test 1",
            "session_date": "2025-03-01",
            "telemetry_data": {},
            "ai_insights": {"summary": "Session test 1", "score": 75},
            "lap_count": 12,
        },
        {
            "user_id": current_user,
            "track_name": "Circuit Test 2",
            "session_date": "2025-03-05",
            "telemetry_data": {},
            "ai_insights": {"summary": "Session test 2", "score": 82},
            "lap_count": 15,
        },
        {
            "user_id": current_user,
            "track_name": "Circuit Test 3",
            "session_date": "2025-03-08",
            "telemetry_data": {},
            "ai_insights": {"summary": "Session test 3", "score": 78},
            "lap_count": 10,
        },
    ]
    try:
        supabase.table("analyses").insert(fake_analyses).execute()
        logger.info(
            "test_data_created",
            extra={
                "user_id": current_user,
                "ip": request.client.host if request.client else None,
                "count": 3,
            },
        )
        return JSONResponse(content={"ok": True, "inserted": 3})
    except Exception as e:
        logger.exception("create_test_data failed for user_id=%s: %s", current_user, e)
        raise HTTPException(status_code=500, detail="Erreur lors de l'insertion des données test")
