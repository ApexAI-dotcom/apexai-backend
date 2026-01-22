#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Stripe Integration Routes
Endpoints pour la gestion des abonnements Stripe
"""

from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import stripe
import os
import logging
# Supabase import optionnel (fait dans la section configuration)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["stripe"])

# Configuration Stripe depuis variables d'environnement
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_51SrmwCJY5DvWR2lK8NNjODvfAMcBxOgjGJv2Zz4ruZeGf1cXGEzWgKIlHjzppYbBYzbHW9wLkwI93ZHiX7oNZZaR00TMOYxrZr")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_cf09094bdeb1196ce9dcddde6422618eee77f327c4dcd0fd047e75be794bb493")

if not STRIPE_SECRET_KEY:
    logger.warning("⚠ Warning: STRIPE_SECRET_KEY not set in environment variables")
else:
    stripe.api_key = STRIPE_SECRET_KEY
    logger.info(f"✓ Stripe API key configured (length: {len(STRIPE_SECRET_KEY)})")

# Configuration Supabase (optionnel - ne crash pas si non disponible)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://vlqpljewmujlnxjuqetv.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODkxNzE5MCwiZXhwIjoyMDg0NDkzMTkwfQ.0K3eoXvvyu6Ga3q1NUlKml8QsFduAiA7RNiBEu0s3Us")

supabase_client = None
try:
    from supabase import create_client, Client
    if SUPABASE_SERVICE_KEY and SUPABASE_SERVICE_KEY != "ton_service_role_key":
        supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("✓ Supabase client configured")
    else:
        logger.warning("⚠ SUPABASE_SERVICE_KEY not configured, Supabase sync disabled")
except ImportError:
    logger.warning("⚠ supabase package not installed, Supabase sync disabled (pip install supabase)")
except Exception as e:
    logger.warning(f"⚠ Could not initialize Supabase client: {e} - Supabase sync disabled")
    supabase_client = None

# TES VRAIS PRICES
PRICE_IDS = {
    "pro_monthly": "price_1SrnvFJY5DvWR2lKaJ7Fg0aY",
    "team_monthly": "price_1SrnvuJY5DvWR2lKeHBwJdSc"
}

# Mapping des plans avec prix
PLAN_MAPPING = {
    "pro": {"amount": 2900, "currency": "eur", "name": "Pro"},  # 29€
    "team": {"amount": 9900, "currency": "eur", "name": "Team"},  # 99€
}

# Cache local pour users PRO (bypass Supabase)
PRO_USERS_CACHE = set()  # Set de user_ids qui ont PRO activé


# ============================================================================
# MODELS
# ============================================================================

class CreateCheckoutSessionRequest(BaseModel):
    plan: str  # "pro" | "team"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CustomerPortalRequest(BaseModel):
    user_id: str
    customer_id: str


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    try:
        try:
            data = await request.json()
        except:
            data = {}
        
        plan = data.get("plan", "pro_monthly")
        print(f"📦 Plan demandé: {plan}")
        logger.info(f"Creating checkout session for plan: {plan}")
        
        price_id = PRICE_IDS.get(plan)
        if not price_id:
            logger.error(f"Plan {plan} non trouvé dans PRICE_IDS")
            return JSONResponse(
                status_code=400,
                content={"error": f"Plan {plan} non trouvé"}
            )
        
        print(f"💳 Price ID: {price_id}")
        logger.info(f"Creating Stripe checkout session with price_id: {price_id}")
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url='http://localhost:8080/?success=true&session_id={CHECKOUT_SESSION_ID}',
            cancel_url='http://localhost:8080/pricing?canceled=true',
        )
        
        print(f"✅ Session créée: {session.id}")
        logger.info(f"Checkout session created: {session.id}")
        
        return JSONResponse(content={"url": session.url})
        
    except stripe.error.StripeError as e:
        error_msg = f"Erreur Stripe: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"❌ STRIPE ERROR: {e}")
        return JSONResponse(
            status_code=400,
            content={"error": error_msg}
        )
    except Exception as e:
        error_msg = f"Erreur serveur: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"❌ ERREUR: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )


@router.get("/customer-portal")
async def get_customer_portal(
    user_id: str,
    customer_id: str
):
    """
    Crée une session Customer Portal pour gérer l'abonnement.
    
    Récupère le Stripe customer depuis Supabase user_metadata.
    
    Args:
        user_id: ID de l'utilisateur Supabase
        customer_id: ID du customer Stripe
    
    Returns:
    {
        "url": "https://billing.stripe.com/..."
    }
    """
    try:
        if not STRIPE_SECRET_KEY:
            raise HTTPException(
                status_code=500,
                detail="Stripe n'est pas configuré. STRIPE_SECRET_KEY manquant."
            )
        
        # Vérifier que le customer existe
        try:
            customer = stripe.Customer.retrieve(customer_id)
            if customer.metadata.get("user_id") and customer.metadata.get("user_id") != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Accès non autorisé à ce customer"
                )
        except stripe.error.StripeError as e:
            logger.error(f"Erreur lors de la récupération du customer: {str(e)}")
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
            "url": portal_session.url,
        })
    
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        logger.error(f"Erreur Stripe: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Erreur Stripe: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Erreur lors de la création de la session portal: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la création de la session: {str(e)}"
        )


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        event_type = event['type']
        print(f"✅ Webhook reçu: {event_type}")
        logger.info(f"Webhook received: {event_type}")
        
        if event_type == 'checkout.session.completed':
            session = event['data']['object']
            customer_id = session.get('customer')
            subscription_id = session.get('subscription')
            session_id = session.get('id')
            
            print(f"📦 Checkout Session ID: {session_id}")
            print(f"👤 Customer ID: {customer_id}")
            print(f"💳 Subscription ID: {subscription_id}")
            logger.info(f"Checkout completed - Session: {session_id}, Customer: {customer_id}, Subscription: {subscription_id}")
            
            # Détecter le plan depuis line_items
            line_items = session.get('line_items', {}).get('data', []) if 'line_items' in session else []
            plan = "pro"  # Par défaut
            if line_items:
                price_id = line_items[0].get('price', {}).get('id', '')
                if 'team' in price_id or price_id == PRICE_IDS.get('team_monthly'):
                    plan = "team"
                elif 'pro' in price_id or price_id == PRICE_IDS.get('pro_monthly'):
                    plan = "pro"
            
            print(f"📋 Plan détecté: {plan}")
            
            # Récupère user depuis metadata
            metadata = session.get('metadata', {})
            user_id = metadata.get('user_id', 'eb4eadbb-b062-43a5-889a-204f5fc4e3eb')
            
            print(f"🔑 User ID: {user_id}")
            logger.info(f"Updating user {user_id} to plan {plan}")
            
            # UPDATE SUPABASE
            if supabase_client:
                try:
                    supabase_client.auth.admin.update_user_by_id(
                        user_id,
                        {"user_metadata": {
                            "subscription": {
                                "plan": plan,
                                "status": "active", 
                                "customer_id": customer_id,
                                "subscription_id": subscription_id
                            }
                        }}
                    )
                    print(f"🎉 PRO SUPABASE ACTIVÉ: {user_id} → {plan}")
                    logger.info(f"✅ Supabase updated: user {user_id} → plan {plan}")
                except Exception as supabase_error:
                    logger.error(f"❌ Error updating Supabase: {supabase_error}", exc_info=True)
                    print(f"❌ Supabase update error: {supabase_error}")
            else:
                logger.warning("⚠ Supabase client not configured, skipping update")
                print("⚠ Supabase non configuré - utilisez /api/set-pro pour activer PRO manuellement")
            
        return JSONResponse(content={"status": "success"})
    except ValueError as e:
        error_msg = f"Invalid payload: {str(e)}"
        logger.error(error_msg)
        print(f"❌ Webhook error (payload): {e}")
        raise HTTPException(status_code=400, detail=error_msg)
    except stripe.error.SignatureVerificationError as e:
        error_msg = f"Invalid signature: {str(e)}"
        logger.error(error_msg)
        print(f"❌ Webhook error (signature): {e}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"Webhook error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=400, detail=error_msg)


@router.get("/set-pro")
async def set_pro(user_id: str):
    """
    Endpoint manuel pour activer PRO instantanément (pour tests/dev).
    BYPASS Supabase - Force PRO en local cache.
    
    Args:
        user_id: ID de l'utilisateur Supabase
    
    Returns:
        {"status": "pro_activated", "user_id": user_id}
    """
    try:
        # BYPASS SUPABASE → LOCAL STATE
        PRO_USERS_CACHE.add(user_id)
        logger.info(f"PRO forced for user: {user_id}")
        print(f"🚀 PRO FORCED: {user_id}")
        return JSONResponse(content={
            "status": "pro_activated",
            "user_id": user_id,
            "plan": "pro",
            "message": "PRO activé (bypass Supabase)"
        })
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in set_pro: {error_msg}", exc_info=True)
        print(f"❌ Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )


@router.get("/test-supabase")
async def test_supabase():
    """
    Endpoint de test pour vérifier la connexion Supabase.
    Teste l'accès à la table profiles.
    
    Returns:
        {"status": "OK", "profiles": count} ou {"error": "message"}
    """
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        result = supabase.table("profiles").select("id").limit(1).execute()
        logger.info("✅ Supabase connection test successful")
        print(f"✅ Supabase test OK - Profiles accessible: {len(result.data)}")
        return JSONResponse(content={
            "status": "OK",
            "profiles": len(result.data)
        })
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Supabase test error: {error_msg}", exc_info=True)
        print(f"❌ Supabase test error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )


@router.get("/subscription-status")
async def get_subscription_status(user_id: str):
    """
    Récupère le statut de l'abonnement d'un utilisateur.
    
    Vérifie d'abord le cache local PRO, puis Supabase/Stripe.
    
    Args:
        user_id: ID de l'utilisateur Supabase
    
    Returns:
    {
        "plan": "free" | "pro" | "team",
        "status": "active" | "canceled" | "past_due",
        "customer_id": "string" | null
    }
    """
    try:
        # Vérifier d'abord le cache local (bypass Supabase)
        if user_id in PRO_USERS_CACHE:
            logger.info(f"User {user_id} found in PRO cache")
            print(f"✅ PRO from cache: {user_id}")
            return JSONResponse(content={
                "plan": "pro",
                "status": "active",
                "customer_id": None,
            })
        
        # TODO: Récupérer depuis Supabase le customer_id et le plan
        # Pour l'instant, on retourne free par défaut
        # Exemple avec Supabase:
        # user = supabase.auth.admin.get_user_by_id(user_id)
        # subscription_data = user.user_metadata.get("subscription", {})
        # customer_id = subscription_data.get("customer_id")
        # 
        # if customer_id:
        #     customer = stripe.Customer.retrieve(customer_id)
        #     subscriptions = stripe.Subscription.list(customer=customer_id, limit=1)
        #     if subscriptions.data:
        #         sub = subscriptions.data[0]
        #         return {
        #             "plan": sub.metadata.get("plan", "free"),
        #             "status": sub.status,
        #             "customer_id": customer_id
        #         }
        
        return JSONResponse(content={
            "plan": "free",  # free, pro, team
            "status": "active",  # active, canceled, past_due
            "customer_id": None,
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération du statut: {str(e)}"
        )
