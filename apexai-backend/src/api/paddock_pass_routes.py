#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Paddock Pass 24h (activation d'un code par un pilote)

Un code distribué sur les circuits (papier ou QR) débloque l'intégralité
des fonctionnalités Premium pendant une durée limitée.

Garde-fous — toute la validation est SERVEUR :
  * le code doit exister, être actif, non expiré, sous son quota ;
  * un pilote ne peut activer un code donné qu'une seule fois (contrainte
    UNIQUE en base) et ne peut pas cumuler s'il a déjà un essai en cours ;
  * un abonné payant n'est jamais dégradé (l'essai ne fait que surclasser).
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client, create_client

from .auth import get_current_user
from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/paddock-pass", tags=["paddock-pass"])

SUPABASE_URL = os.getenv("SUPABASE_URL") or getattr(settings, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
)

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_SERVICE_ROLE_KEY not in ("", "ton_service_role_key"):
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


class RedeemRequest(BaseModel):
    code: str


def _parse_dt(raw) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = raw if hasattr(raw, "year") else datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


@router.get("/status")
async def pass_status(current_user: str = Depends(get_current_user)):
    """Essai en cours pour ce pilote (pour le compte à rebours dans l'app)."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Service indisponible")
    try:
        res = supabase.table("profiles").select("trial_tier, trial_until").eq("id", current_user).limit(1).execute()
        if not res.data:
            return {"active": False}
        until = _parse_dt(res.data[0].get("trial_until"))
        now = datetime.now(timezone.utc)
        if until and until > now:
            return {
                "active": True,
                "tier": res.data[0].get("trial_tier"),
                "until": until.isoformat(),
                "seconds_left": int((until - now).total_seconds()),
            }
        return {"active": False}
    except Exception as e:
        logger.error(f"pass_status failed: {e}")
        return {"active": False}


@router.post("/redeem")
async def redeem(payload: RedeemRequest, current_user: str = Depends(get_current_user)):
    """Activer un Paddock Pass."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Service indisponible")

    code = (payload.code or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Code manquant.")

    now = datetime.now(timezone.utc)

    # 1. Le code existe-t-il et est-il utilisable ?
    try:
        res = supabase.table("promo_codes").select("*").eq("code", code).limit(1).execute()
    except Exception as e:
        logger.error(f"redeem lookup failed: {e}")
        raise HTTPException(status_code=500, detail="Vérification impossible.")

    if not res.data:
        raise HTTPException(status_code=404, detail="Ce code n'existe pas.")
    promo = res.data[0]

    if not promo.get("active"):
        raise HTTPException(status_code=400, detail="Ce Paddock Pass n'est plus actif.")
    expires_at = _parse_dt(promo.get("expires_at"))
    if expires_at and expires_at < now:
        raise HTTPException(status_code=400, detail="Ce Paddock Pass a expiré.")
    max_red = promo.get("max_redemptions")
    if max_red is not None and int(promo.get("redemptions") or 0) >= int(max_red):
        raise HTTPException(status_code=400, detail="Ce Paddock Pass a atteint sa limite d'utilisations.")

    # 2. Le pilote a-t-il déjà utilisé CE code, ou un essai en cours ?
    try:
        already = supabase.table("promo_redemptions").select("id") \
            .eq("code", code).eq("user_id", current_user).limit(1).execute()
        if already.data:
            raise HTTPException(status_code=400, detail="Vous avez déjà utilisé ce Paddock Pass.")

        prof = supabase.table("profiles").select("trial_until, subscription_tier") \
            .eq("id", current_user).limit(1).execute()
        current_trial = _parse_dt(prof.data[0].get("trial_until")) if prof.data else None
        if current_trial and current_trial > now:
            raise HTTPException(status_code=400, detail="Un Paddock Pass est déjà en cours sur votre compte.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"redeem checks failed: {e}")
        raise HTTPException(status_code=500, detail="Vérification impossible.")

    # 3. Activation
    trial_until = now + timedelta(hours=int(promo.get("duration_hours") or 24))
    tier = (promo.get("tier") or "racer").lower()
    try:
        supabase.table("profiles").update({
            "trial_tier": tier,
            "trial_until": trial_until.isoformat(),
        }).eq("id", current_user).execute()

        supabase.table("promo_redemptions").insert({
            "code": code,
            "user_id": current_user,
            "trial_until": trial_until.isoformat(),
        }).execute()

        supabase.table("promo_codes").update({
            "redemptions": int(promo.get("redemptions") or 0) + 1
        }).eq("code", code).execute()

        logger.info(f"paddock pass {code} redeemed by {current_user} until {trial_until.isoformat()}")
        return {
            "success": True,
            "tier": tier,
            "until": trial_until.isoformat(),
            "duration_hours": promo.get("duration_hours"),
        }
    except Exception as e:
        logger.error(f"redeem activation failed: {e}")
        raise HTTPException(status_code=500, detail="Activation impossible.")
