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
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

supabase_client = None
try:
    from supabase import Client, create_client

    if SUPABASE_URL and SUPABASE_SERVICE_KEY and SUPABASE_SERVICE_KEY != "ton_service_role_key":
        supabase_client: Optional[Client] = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("Supabase client configured for Stripe routes")
    else:
        supabase_client = None
except ImportError:
    logger.warning("supabase not installed, Stripe sync disabled")
except Exception as e:
    logger.warning("Supabase init failed: %s", e)
    supabase_client = None

# Price IDs : racer_monthly/annual, team_monthly/annual (configurables via env)
PRICE_IDS = {
    "racer_monthly": os.getenv("STRIPE_PRICE_RACER_MONTHLY", "price_1SrnvFJY5DvWR2lKaJ7Fg0aY"),
    "racer_annual": os.getenv("STRIPE_PRICE_RACER_ANNUAL", ""),
    "team_monthly": os.getenv("STRIPE_PRICE_TEAM_MONTHLY", "price_1SrnvuJY5DvWR2lKeHBwJdSc"),
    "team_annual": os.getenv("STRIPE_PRICE_TEAM_ANNUAL", ""),
}

# Mapping price_id -> (tier, billing_period) pour le webhook
def _price_id_to_tier_and_period(price_id: str) -> tuple[str, str]:
    if not price_id:
        return "rookie", "monthly"
    pid = price_id.strip()
    if pid == PRICE_IDS.get("racer_monthly"):
        return "racer", "monthly"
    if pid == PRICE_IDS.get("racer_annual"):
        return "racer", "annual"
    if pid == PRICE_IDS.get("team_monthly"):
        return "team", "monthly"
    if pid == PRICE_IDS.get("team_annual"):
        return "team", "annual"
    if "team" in pid.lower():
        return "team", "annual" if "annual" in pid.lower() else "monthly"
    if "racer" in pid.lower() or "pro" in pid.lower():
        return "racer", "annual" if "annual" in pid.lower() else "monthly"
    return "racer", "monthly"


# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------

class CreateCheckoutSessionRequest(BaseModel):
    user_id: str
    price_id: str  # racer_monthly | racer_annual | team_monthly | team_annual


class CreatePortalSessionRequest(BaseModel):
    user_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/create-checkout-session")
async def create_checkout_session(body: CreateCheckoutSessionRequest) -> JSONResponse:
    """
    Crée une session Stripe Checkout. Retourne checkout_url.
    Idempotence : 400 si l'utilisateur a déjà un abonnement actif.
    """
    try:
        user_id = body.user_id.strip()
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
                    .eq("id", user_id)
                    .limit(1)
                    .execute()
                )
                if r.data and len(r.data) > 0:
                    row = r.data[0]
                    if row.get("subscription_status") == "active" and row.get("stripe_subscription_id"):
                        logger.warning("create_checkout_session: user %s already subscribed", user_id)
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
            metadata={"user_id": user_id},
        )
        logger.info("create_checkout_session: session_id=%s user_id=%s", session.id, user_id)
        return JSONResponse(content={"checkout_url": session.url})
    except stripe.error.StripeError as e:
        logger.error("create_checkout_session StripeError: %s", e, exc_info=True)
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.exception("create_checkout_session: %s", e)
        return JSONResponse(status_code=500, content={"error": "Erreur serveur"})


@router.post("/create-portal-session")
async def create_portal_session(body: CreatePortalSessionRequest) -> JSONResponse:
    """
    Crée une session Stripe Customer Portal à partir du user_id.
    Récupère stripe_customer_id depuis la table profiles.
    """
    try:
        user_id = body.user_id.strip()
        if not STRIPE_SECRET_KEY:
            return JSONResponse(status_code=500, content={"error": "Stripe non configuré"})
        if not supabase_client:
            return JSONResponse(status_code=503, content={"error": "Service indisponible"})
        r = (
            supabase_client.table("profiles")
            .select("stripe_customer_id")
            .eq("id", user_id)
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
        logger.info("create_portal_session: user_id=%s", user_id)
        return JSONResponse(content={"portal_url": portal_session.url})
    except stripe.error.StripeError as e:
        logger.error("create_portal_session StripeError: %s", e, exc_info=True)
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        logger.exception("create_portal_session: %s", e)
        return JSONResponse(status_code=500, content={"error": "Erreur serveur"})


@router.get("/customer-portal")
async def get_customer_portal(user_id: str, customer_id: str) -> JSONResponse:
    """
    Legacy: crée une session Portal à partir de user_id + customer_id (query params).
    Préférer POST /api/stripe/create-portal-session avec { user_id }.
    """
    try:
        if not STRIPE_SECRET_KEY:
            raise HTTPException(status_code=500, detail="Stripe non configuré")
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


@router.post("/webhook")
async def stripe_webhook(request: Request) -> JSONResponse:
    """
    Webhook Stripe. Écrit UNIQUEMENT dans la table profiles.
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
    logger.info("stripe_webhook_event %s", json.dumps({"event_type": event_type, "event_id": event_id}))

    try:
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            customer_id = session.get("customer")
            subscription_id = session.get("subscription")
            metadata = session.get("metadata") or {}
            user_id = (metadata.get("user_id") or "").strip()
            if not user_id:
                logger.warning(
                    "webhook checkout.session.completed: user_id missing, session_id=%s",
                    session.get("id"),
                )
                return JSONResponse(content={"received": True})

            # Dériver tier + billing_period depuis le price_id
            tier, billing_period = "racer", "monthly"
            if subscription_id:
                try:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    if sub.get("items") and sub["items"].get("data"):
                        price_id = sub["items"]["data"][0].get("price", {}).get("id", "")
                        tier, billing_period = _price_id_to_tier_and_period(price_id)
                    start_ts = sub.get("current_period_start")
                    end_ts = sub.get("current_period_end")
                    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc) if start_ts else None
                    end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc) if end_ts else None
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
                except Exception as e:
                    logger.exception("webhook checkout.session.completed update failed: %s", e)
            else:
                _update_profile_subscription(
                    user_id,
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=subscription_id,
                    subscription_tier=tier,
                    billing_period=billing_period,
                    subscription_status="active",
                )
            logger.info("webhook checkout.session.completed processed user_id=%s tier=%s", user_id, tier)

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
        raise HTTPException(status_code=500, detail="Webhook handler failed")


@router.get("/set-pro")
async def set_pro(user_id: str) -> JSONResponse:
    """Dev/test only: force PRO in local cache. Ne pas utiliser en production."""
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
    if not supabase_client:
        return JSONResponse(status_code=503, content={"error": "Supabase non configuré"})
    try:
        r = supabase_client.table("profiles").select("id").limit(1).execute()
        return JSONResponse(content={"status": "OK", "profiles_count": len(r.data or [])})
    except Exception as e:
        logger.exception("test_supabase: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
