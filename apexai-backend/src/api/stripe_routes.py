#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Stripe Integration Routes
Endpoints pour la gestion des abonnements Stripe.
Source de vérité : table profiles (jamais auth.users.user_metadata).
"""

from datetime import datetime, timezone
from typing import Optional

import json
import logging
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .auth import get_current_user
from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stripe", tags=["stripe"])

# Configuration Stripe : pas de valeur par défaut en dur (sécurité)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
    logger.info("Stripe API key configured")
else:
    logger.warning("STRIPE_SECRET_KEY not set")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
# Webhook DOIT utiliser service_role pour bypasser RLS (écriture dans profiles)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

from supabase import Client, create_client

supabase_client: Optional[Client]
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_KEY in ("", "ton_service_role_key"):
    logger.error(
        "Supabase client is None - check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY)"
    )
    supabase_client = None
else:
    supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    logger.info("Supabase client initialized: %s", SUPABASE_URL)

# Price IDs : env vars UNIQUEMENT (pas de fallback hardcodé)
STRIPE_PRICE_RACER_MONTHLY = (os.getenv("STRIPE_PRICE_RACER_MONTHLY") or "").strip()
STRIPE_PRICE_RACER_ANNUAL = (os.getenv("STRIPE_PRICE_RACER_ANNUAL") or "").strip()
STRIPE_PRICE_TEAM_MONTHLY = (os.getenv("STRIPE_PRICE_TEAM_MONTHLY") or "").strip()
STRIPE_PRICE_TEAM_ANNUAL = (os.getenv("STRIPE_PRICE_TEAM_ANNUAL") or "").strip()

if not STRIPE_PRICE_RACER_MONTHLY:
    raise RuntimeError("Missing STRIPE_PRICE_*")

PRICE_IDS = {
    "racer_monthly": STRIPE_PRICE_RACER_MONTHLY,
    "racer_annual": STRIPE_PRICE_RACER_ANNUAL,
    "team_monthly": STRIPE_PRICE_TEAM_MONTHLY,
    "team_annual": STRIPE_PRICE_TEAM_ANNUAL,
}

logger.info("prices_loaded", extra={"racer_monthly": STRIPE_PRICE_RACER_MONTHLY})

# Mapping exact price_id -> (tier, billing_period) pour le webhook (log si inconnu)
def _build_price_to_tier() -> dict:
    out = {}
    for key, pid in PRICE_IDS.items():
        if pid:
            out[pid.strip()] = (
                "racer" if "racer" in key else "team",
                "annual" if "annual" in key else "monthly",
            )
    return out

PRICE_TO_TIER = _build_price_to_tier()

def _price_id_to_tier_and_period(price_id: str) -> tuple[str, str]:
    if not price_id:
        return "rookie", "monthly"
    pid = price_id.strip()
    if pid in PRICE_TO_TIER:
        return PRICE_TO_TIER[pid]
    if "team" in pid.lower():
        return "team", "annual" if "annual" in pid.lower() else "monthly"
    if "racer" in pid.lower() or "pro" in pid.lower():
        return "racer", "annual" if "annual" in pid.lower() else "monthly"
    return "racer", "monthly"


# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------

class CreateCheckoutSessionRequest(BaseModel):
    price_id: str  # racer_monthly | racer_annual | team_monthly | team_annual


class CreatePortalSessionRequest(BaseModel):
    pass  # user_id from JWT (current_user)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: Request,
    body: CreateCheckoutSessionRequest,
    current_user: str = Depends(get_current_user),
) -> JSONResponse:
    """
    Crée une session Stripe Checkout. Auth JWT obligatoire.
    Idempotence : 400 si l'utilisateur a déjà un abonnement actif.
    """
    try:
        logger.info(
            "user_action",
            extra={
                "action": "checkout_session",
                "user_id": current_user,
                "ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )
        price_id_key = body.price_id.strip()
        if price_id_key not in PRICE_IDS:
            logger.warning("create_checkout_session: invalid price_id=%s", price_id_key)
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_price_id",
                    "message": f"Price ID non reconnu: {price_id_key}",
                },
            )
        stripe_price_id = PRICE_IDS.get(price_id_key)
        if not stripe_price_id:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_price_id", "message": "Price ID non configuré"},
            )

        if supabase_client:
            try:
                r = (
                    supabase_client.table("profiles")
                    .select("subscription_status", "stripe_subscription_id")
                    .eq("id", current_user)
                    .limit(1)
                    .execute()
                )
                if r.data and len(r.data) > 0:
                    row = r.data[0]
                    if row.get("subscription_status") == "active" and row.get("stripe_subscription_id"):
                        logger.warning("create_checkout_session: user %s already subscribed", current_user)
                        return JSONResponse(
                            status_code=400,
                            content={
                                "error": "already_subscribed",
                                "message": "Vous avez déjà un abonnement actif. Gérer depuis Mon compte.",
                            },
                        )
            except Exception as e:
                logger.warning("create_checkout_session: idempotency check failed: %s", e)

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/?success=true&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/pricing?canceled=true",
            metadata={"user_id": current_user, "supabase_user_id": current_user},
            subscription_data={"metadata": {"user_id": current_user, "supabase_user_id": current_user}},
        )
        logger.info("create_checkout_session: session_id=%s user_id=%s", session.id, current_user)
        return JSONResponse(content={"checkout_url": session.url})
    except stripe.error.StripeError as e:
        logger.error("create_checkout_session StripeError: %s", e, exc_info=True)
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.exception("create_checkout_session: %s", e)
        return JSONResponse(status_code=500, content={"error": "Erreur serveur"})


@router.post("/create-portal-session")
async def create_portal_session(
    request: Request,
    current_user: str = Depends(get_current_user),
) -> JSONResponse:
    """
    Crée une session Stripe Customer Portal. Auth JWT obligatoire.
    Récupère stripe_customer_id depuis la table profiles.
    """
    try:
        logger.info(
            "user_action",
            extra={
                "action": "portal_session",
                "user_id": current_user,
                "ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )
        if not STRIPE_SECRET_KEY:
            return JSONResponse(status_code=500, content={"error": "Stripe non configuré"})
        if not supabase_client:
            return JSONResponse(status_code=503, content={"error": "Service indisponible"})
        r = (
            supabase_client.table("profiles")
            .select("stripe_customer_id")
            .eq("id", current_user)
            .limit(1)
            .execute()
        )
        if not r.data or len(r.data) == 0:
            return JSONResponse(
                status_code=404,
                content={"error": "no_customer", "message": "Aucun abonnement associé à ce compte."},
            )
        customer_id = (r.data[0] or {}).get("stripe_customer_id")
        if not customer_id:
            return JSONResponse(
                status_code=400,
                content={"error": "no_customer", "message": "Aucun abonnement associé à ce compte."},
            )
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{FRONTEND_URL}/profile",
        )
        logger.info("create_portal_session: user_id=%s", current_user)
        return JSONResponse(content={"portal_url": portal_session.url})
    except stripe.error.StripeError as e:
        logger.error("create_portal_session StripeError: %s", e, exc_info=True)
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.exception("create_portal_session: %s", e)
        return JSONResponse(status_code=500, content={"error": "Erreur serveur"})


@router.get("/customer-portal")
async def get_customer_portal(
    request: Request,
    current_user: str = Depends(get_current_user),
) -> JSONResponse:
    """
    Crée une session Portal pour l'utilisateur authentifié. Auth JWT obligatoire.
    Récupère stripe_customer_id depuis profiles.
    """
    try:
        logger.info(
            "user_action",
            extra={
                "action": "customer_portal",
                "user_id": current_user,
                "ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )
        if not STRIPE_SECRET_KEY:
            raise HTTPException(status_code=500, detail="Stripe non configuré")
        if not supabase_client:
            raise HTTPException(status_code=503, detail="Service indisponible")
        r = (
            supabase_client.table("profiles")
            .select("stripe_customer_id")
            .eq("id", current_user)
            .limit(1)
            .execute()
        )
        if not r.data or len(r.data) == 0:
            raise HTTPException(status_code=404, detail="Aucun abonnement associé à ce compte.")
        customer_id = (r.data[0] or {}).get("stripe_customer_id")
        if not customer_id:
            raise HTTPException(status_code=404, detail="Aucun abonnement associé à ce compte.")
        stripe.Customer.retrieve(customer_id)
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{FRONTEND_URL}/profile",
        )
        return JSONResponse(content={"url": portal_session.url})
    except stripe.error.InvalidRequestError:
        raise HTTPException(status_code=404, detail="Customer non trouvé")
    except stripe.error.StripeError as e:
        logger.error("customer_portal StripeError: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


def _update_profile_subscription(
    user_id: str,
    *,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    subscription_tier: Optional[str] = None,
    billing_period: Optional[str] = None,
    subscription_status: Optional[str] = None,
    subscription_start_date: Optional[datetime] = None,
    subscription_end_date: Optional[datetime] = None,
) -> None:
    """Met à jour uniquement la table profiles (jamais user_metadata)."""
    if not supabase_client:
        return
    payload: dict = {}
    if stripe_customer_id is not None:
        payload["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id is not None:
        payload["stripe_subscription_id"] = stripe_subscription_id
    if subscription_tier is not None:
        payload["subscription_tier"] = subscription_tier
    if billing_period is not None:
        payload["billing_period"] = billing_period
    if subscription_status is not None:
        payload["subscription_status"] = subscription_status
    if subscription_start_date is not None:
        payload["subscription_start_date"] = subscription_start_date.isoformat()
    if subscription_end_date is not None:
        payload["subscription_end_date"] = subscription_end_date.isoformat()
    if not payload:
        return
    try:
        supabase_client.table("profiles").update(payload).eq("id", user_id).execute()
        logger.info("profiles updated for user_id=%s keys=%s", user_id, list(payload.keys()))
    except Exception as e:
        logger.exception("_update_profile_subscription failed: %s", e)


def _log_webhook(step: str, **kwargs: object) -> None:
    """Log structuré JSON pour le webhook."""
    logger.info("stripe_webhook %s", json.dumps({"step": step, **kwargs}))


@router.post("/webhook")
async def stripe_webhook(request: Request) -> JSONResponse:
    """
    Webhook Stripe. Écrit UNIQUEMENT dans la table profiles (via service_role).
    Événements : checkout.session.completed, customer.subscription.updated, customer.subscription.deleted.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set, rejecting webhook")
        raise HTTPException(status_code=500, detail="Webhook not configured")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError as e:
        logger.warning("Webhook invalid payload: %s", e)
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.warning("Webhook invalid signature: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.get("type", "")
    event_id = event.get("id", "")
    _log_webhook("event_received", event_type=event_type, event_id=event_id)

    try:
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            session_id = session.get("id", "")
            metadata = session.get("metadata") or {}
            _log_webhook("session_metadata", session_id=session_id, metadata=metadata)

            user_id = (metadata.get("user_id") or metadata.get("supabase_user_id") or "").strip()
            if not user_id:
                logger.warning(
                    "stripe_webhook user_id missing from metadata session_id=%s",
                    session_id,
                    extra={"step": "user_id_extract", "metadata": metadata},
                )
                _log_webhook("user_id_missing", session_id=session_id)
                return JSONResponse(content={"received": True})

            _log_webhook("user_id_extracted", user_id=user_id, session_id=session_id)

            customer_id = session.get("customer")
            subscription_id = session.get("subscription")
            tier, billing_period = "racer", "monthly"
            start_dt, end_dt = None, None

            if subscription_id:
                try:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    items_data = sub.get("items") or {}
                    data_list = items_data.get("data") or []
                    _log_webhook(
                        "subscription_retrieved",
                        subscription_id=subscription_id,
                        items_data_len=len(data_list),
                    )
                    if data_list:
                        first_item = data_list[0]
                        price_obj = first_item.get("price") or {}
                        price_id = (price_obj.get("id") or "").strip()
                        _log_webhook(
                            "price_id_extracted",
                            subscription_id=subscription_id,
                            price_id=price_id,
                            known_price_ids=list(PRICE_TO_TIER.keys()),
                        )
                        tier, billing_period = _price_id_to_tier_and_period(price_id)
                        if price_id and price_id not in PRICE_TO_TIER:
                            logger.error(
                                "stripe_webhook unknown price_id: %s (subscription_id=%s)",
                                price_id,
                                subscription_id,
                                extra={"step": "price_mapping", "price_id": price_id},
                            )
                            _log_webhook(
                                "price_mapping_failed",
                                subscription_id=subscription_id,
                                price_id=price_id,
                                items_data=data_list,
                                known_price_ids=list(PRICE_TO_TIER.keys()),
                            )
                    start_ts = sub.get("current_period_start")
                    end_ts = sub.get("current_period_end")
                    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc) if start_ts else None
                    end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc) if end_ts else None
                except Exception as sub_err:
                    logger.exception(
                        "stripe_webhook subscription retrieve failed: %s (subscription_id=%s)",
                        sub_err,
                        subscription_id,
                    )
                    _log_webhook("subscription_retrieve_error", error=str(sub_err), subscription_id=subscription_id)

            _log_webhook("tier_determined", user_id=user_id, tier=tier, billing_period=billing_period)

            update_payload = {
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "subscription_tier": tier,
                "billing_period": billing_period,
                "subscription_status": "active",
                "subscription_start_date": start_dt.isoformat() if start_dt else None,
                "subscription_end_date": end_dt.isoformat() if end_dt else None,
            }
            _log_webhook("update_before", user_id=user_id, payload=update_payload)

            if supabase_client:
                try:
                    _update_profile_subscription(
                        user_id,
                        stripe_customer_id=customer_id,
                        stripe_subscription_id=subscription_id,
                        subscription_tier=tier,
                        billing_period=billing_period,
                        subscription_status="active",
                        subscription_start_date=start_dt,
                        subscription_end_date=end_dt,
                    )
                    _log_webhook("update_after", user_id=user_id, status="ok", count=1, success=True)
                except Exception as update_err:
                    logger.exception(
                        "stripe_webhook profiles update failed: %s (user_id=%s)",
                        update_err,
                        user_id,
                    )
                    _log_webhook("update_after", user_id=user_id, status="error", error=str(update_err))
            else:
                _log_webhook("update_skipped", user_id=user_id, reason="supabase_client_none")

        elif event_type == "customer.subscription.updated":
            sub = event["data"]["object"]
            subscription_id = sub.get("id")
            customer_id = sub.get("customer")
            status = (sub.get("status") or "").strip() or None
            tier, billing_period = "racer", "monthly"
            if sub.get("items") and sub["items"].get("data"):
                price_id = sub["items"]["data"][0].get("price", {}).get("id", "")
                tier, billing_period = _price_id_to_tier_and_period(price_id)
            start_ts = sub.get("current_period_start")
            end_ts = sub.get("current_period_end")
            start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc) if start_ts else None
            end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc) if end_ts else None

            if not supabase_client:
                return JSONResponse(content={"received": True})
            r = (
                supabase_client.table("profiles")
                .select("id")
                .eq("stripe_subscription_id", subscription_id)
                .limit(1)
                .execute()
            )
            if r.data and len(r.data) > 0:
                user_id = r.data[0]["id"]
                _update_profile_subscription(
                    user_id,
                    subscription_tier=tier,
                    billing_period=billing_period,
                    subscription_status=status,
                    subscription_start_date=start_dt,
                    subscription_end_date=end_dt,
                )
                logger.info("webhook customer.subscription.updated user_id=%s status=%s", user_id, status)
            else:
                logger.warning("webhook customer.subscription.updated: no profile for subscription_id=%s", subscription_id)

        elif event_type == "customer.subscription.deleted":
            sub = event["data"]["object"]
            subscription_id = sub.get("id")
            if not supabase_client:
                return JSONResponse(content={"received": True})
            r = (
                supabase_client.table("profiles")
                .select("id")
                .eq("stripe_subscription_id", subscription_id)
                .limit(1)
                .execute()
            )
            if r.data and len(r.data) > 0:
                user_id = r.data[0]["id"]
                _update_profile_subscription(
                    user_id,
                    subscription_status="canceled",
                    subscription_tier="rookie",
                    stripe_subscription_id=None,
                    subscription_end_date=datetime.now(timezone.utc),
                )
                logger.info("webhook customer.subscription.deleted user_id=%s", user_id)
            else:
                logger.warning("webhook customer.subscription.deleted: no profile for subscription_id=%s", subscription_id)

        return JSONResponse(content={"received": True})
    except Exception as e:
        logger.exception("stripe_webhook handler: %s", e)
        _log_webhook("handler_exception", error=str(e))
        return JSONResponse(content={"received": True})


@router.get("/set-pro")
async def set_pro(user_id: str) -> JSONResponse:
    """Dev/test only: force PRO in local cache. Ne pas utiliser en production."""
    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404, detail="Not Found")
    try:
        if not supabase_client:
            return JSONResponse(status_code=503, content={"error": "Supabase non configuré"})
        supabase_client.table("profiles").update({
            "subscription_tier": "racer",
            "subscription_status": "active",
        }).eq("id", user_id).execute()
        logger.info("set_pro: user_id=%s (profiles updated)", user_id)
        return JSONResponse(content={"status": "pro_activated", "user_id": user_id})
    except Exception as e:
        logger.exception("set_pro: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/test-supabase")
async def test_supabase() -> JSONResponse:
    """Test connexion Supabase (table profiles)."""
    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404, detail="Not Found")
    if not supabase_client:
        return JSONResponse(status_code=503, content={"error": "Supabase non configuré"})
    try:
        r = supabase_client.table("profiles").select("id").limit(1).execute()
        return JSONResponse(content={"status": "OK", "profiles_count": len(r.data or [])})
    except Exception as e:
        logger.exception("test_supabase: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
