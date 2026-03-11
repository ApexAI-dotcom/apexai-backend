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
async def test_data(
    request: Request,
    current_user: str = Depends(get_current_user),
):
    """
    TEMPORAIRE. Insère 3 analyses de test pour current_user (visibles en UI).
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")
    try:
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
        logger.info("test_data_created", extra={"user_id": current_user, "count": 3})
        return {"inserted": 3}
    except Exception as e:
        logger.exception("test_data failed for user_id=%s: %s", current_user, e)
        raise HTTPException(status_code=500, detail="Erreur lors de l'insertion des données test")
