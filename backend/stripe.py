#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ApexAI - Stripe Integration
Endpoints pour la gestion des abonnements Stripe
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import stripe
import os

# Configuration Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
if not STRIPE_SECRET_KEY:
    print("⚠ Warning: STRIPE_SECRET_KEY not set in environment variables")
else:
    stripe.api_key = STRIPE_SECRET_KEY
    print(f"✓ Stripe API key configured (length: {len(STRIPE_SECRET_KEY)})")

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test_placeholder")

router = APIRouter(prefix="/api", tags=["stripe"])


# ============================================================================
# MODELS
# ============================================================================

class CreateCheckoutSessionRequest(BaseModel):
    plan: str  # "pro" | "team"
    user_id: str  # Supabase User ID
    user_email: str
    success_url: str = None  # Optionnel
    cancel_url: str = None  # Optionnel


class CustomerPortalRequest(BaseModel):
    user_id: str
    customer_id: str  # Stripe Customer ID


# ============================================================================
# PRICE IDs (à configurer dans Stripe Dashboard)
# ============================================================================
# Ces IDs doivent être créés dans Stripe Dashboard
# Pour l'instant, on utilise des IDs de test
PRICE_IDS = {
    "free": None,  # Gratuit
    "pro": "price_pro_monthly",  # 29€/mois - À remplacer par le vrai Price ID
    "team": "price_team_monthly",  # 99€/mois - À remplacer par le vrai Price ID
}

# Mapping des plans
PLAN_MAPPING = {
    "pro": {"amount": 2900, "currency": "eur", "name": "Pro"},  # 29€
    "team": {"amount": 9900, "currency": "eur", "name": "Team"},  # 99€
}


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/create-checkout-session")
async def create_checkout_session(request: CreateCheckoutSessionRequest):
    """
    Crée une session Stripe Checkout pour un abonnement.
    
    Body attendu:
    {
        "plan": "pro" | "team",
        "user_id": "string",
        "user_email": "string",
        "success_url": "string" (optionnel),
        "cancel_url": "string" (optionnel)
    }
    """
    """
    Crée une session Stripe Checkout pour un abonnement
    
    Plans disponibles:
    - free: 0€ (gratuit)
    - pro: 29€/mois
    - team: 99€/mois
    """
    try:
        # Valider le plan
        plan = request.plan.lower()
        if plan not in ["pro", "team"]:
            raise HTTPException(
                status_code=400,
                detail=f"Plan invalide: {plan}. Doit être 'pro' ou 'team'"
            )
        
        price_amount = PLAN_MAPPING[plan]["amount"]
        
        # Créer ou récupérer le customer Stripe
        customers = stripe.Customer.list(email=request.user_email, limit=1)
        if customers.data:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(
                email=request.user_email,
                metadata={"user_id": request.user_id}
            )
        
        # Créer la session Checkout
        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": f"APEX AI - Plan {PLAN_MAPPING[plan]['name']}",
                            "description": f"Abonnement mensuel {PLAN_MAPPING[plan]['name']}",
                        },
                        "unit_amount": price_amount,
                        "recurring": {
                            "interval": "month",
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=request.success_url or f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=request.cancel_url or f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/pricing",
            metadata={
                "user_id": request.user_id,
                "plan": plan,
            },
        )
        
        return JSONResponse(content={
            "success": True,
            "session_id": checkout_session.id,
            "url": checkout_session.url,
        })
    
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erreur Stripe: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la création de la session: {str(e)}"
        )


@router.get("/customer-portal")
async def get_customer_portal(
    user_id: str,
    customer_id: str
):
    """
    Crée une session Customer Portal pour gérer l'abonnement
    """
    try:
        # Vérifier que le customer existe
        try:
            customer = stripe.Customer.retrieve(customer_id)
            if customer.metadata.get("user_id") != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Accès non autorisé à ce customer"
                )
        except stripe.error.StripeError:
            raise HTTPException(
                status_code=404,
                detail="Customer non trouvé"
            )
        
        # Créer la session Customer Portal
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/profile",
        )
        
        return JSONResponse(content={
            "success": True,
            "url": portal_session.url,
        })
    
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erreur Stripe: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la création de la session: {str(e)}"
        )


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """
    Webhook Stripe pour gérer les événements d'abonnement
    
    Événements gérés:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Traiter les événements
    event_type = event["type"]
    data = event["data"]["object"]
    
    try:
        if event_type == "customer.subscription.created":
            # Nouvel abonnement créé
            user_id = data.get("metadata", {}).get("user_id")
            plan = data.get("metadata", {}).get("plan", "pro")
            # TODO: Mettre à jour Supabase avec le plan de l'utilisateur
            print(f"Subscription created for user {user_id}, plan: {plan}")
        
        elif event_type == "customer.subscription.updated":
            # Abonnement mis à jour
            user_id = data.get("metadata", {}).get("user_id")
            status = data.get("status")
            # TODO: Mettre à jour Supabase avec le nouveau statut
            print(f"Subscription updated for user {user_id}, status: {status}")
        
        elif event_type == "customer.subscription.deleted":
            # Abonnement annulé
            user_id = data.get("metadata", {}).get("user_id")
            # TODO: Mettre à jour Supabase pour passer à "free"
            print(f"Subscription deleted for user {user_id}")
        
        elif event_type == "invoice.payment_succeeded":
            # Paiement réussi
            customer_id = data.get("customer")
            # TODO: Confirmer le paiement dans Supabase
            print(f"Payment succeeded for customer {customer_id}")
        
        elif event_type == "invoice.payment_failed":
            # Paiement échoué
            customer_id = data.get("customer")
            # TODO: Notifier l'utilisateur du paiement échoué
            print(f"Payment failed for customer {customer_id}")
        
        return JSONResponse(content={"received": True})
    
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing webhook: {str(e)}"
        )


@router.get("/subscription-status")
async def get_subscription_status(user_id: str):
    """
    Récupère le statut de l'abonnement d'un utilisateur
    """
    try:
        # TODO: Récupérer depuis Supabase le customer_id et le plan
        # Pour l'instant, on retourne un mock
        return JSONResponse(content={
            "success": True,
            "plan": "free",  # free, pro, team
            "status": "active",  # active, canceled, past_due
            "customer_id": None,
        })
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération du statut: {str(e)}"
        )
