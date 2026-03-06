# Système d'abonnement Apex AI

Documentation de l'architecture et du flux des abonnements Stripe (tiers Rookie / Racer / Team).

---

## 1. Architecture globale

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend      │     │   Backend         │     │   Stripe        │
│   (React)       │────▶│   (FastAPI)       │────▶│   (API +        │
│                 │     │                   │     │    Webhooks)    │
└────────┬────────┘     └────────┬──────────┘     └────────┬────────┘
         │                       │                        │
         │  JWT (Authorization)  │  service_role          │  webhook
         ▼                       ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Supabase                                                            │
│  • auth.users (auth uniquement)                                       │
│  • public.profiles (source de vérité abo : tier, stripe_*, limits)   │
│  • public.usage_logs (audit)                                          │
└─────────────────────────────────────────────────────────────────────┘
```

- **Source de vérité abonnement** : table `public.profiles` (colonnes `subscription_tier`, `subscription_status`, `stripe_customer_id`, `stripe_subscription_id`, etc.). On ne s'appuie **pas** sur `auth.users.user_metadata` pour les limites ou le tier.
- **Backend** : vérifie les limites via `subscription_service` (lecture/écriture `profiles` avec `service_role`).
- **Stripe** : paiements et portail client ; le webhook Stripe met à jour **uniquement** la table `profiles`.

---

## 2. Flux utilisateur

1. **Souscription**
   - L’utilisateur clique « S’abonner » sur la page Tarifs (Pricing).
   - Le frontend appelle `POST /api/stripe/create-checkout-session` avec `{ user_id, price_id }`.
   - Le backend crée une session Stripe Checkout (avec `metadata.user_id`) et renvoie `{ checkout_url }`.
   - Redirection vers Stripe → paiement → redirection vers `success_url` ou `cancel_url`.

2. **Webhook Stripe**
   - Stripe envoie `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted` à `POST /api/stripe/webhook`.
   - Le backend vérifie la signature, lit `metadata.user_id` (checkout) ou identifie l’utilisateur via `stripe_customer_id` dans `profiles` (subscription.*), puis met à jour **uniquement** la table `profiles` (tier, status, dates, stripe_*).
   - Aucune écriture dans `auth.users.user_metadata`.

3. **Affichage côté app**
   - Le frontend appelle `GET /api/user/subscription` (header `Authorization: Bearer <JWT>`).
   - Le backend dérive le `user_id` du JWT, lit `profiles` + `subscription_service.get_user_limits()` et renvoie `tier`, `status`, `billing_period`, `subscription_end_date`, `limits`.

4. **Limite d’analyses**
   - À chaque analyse : le backend appelle `check_analysis_limit(user_id)` ; si limite atteinte → 403 `limit_reached`.
   - Après une analyse réussie : `increment_analysis_count(user_id)` met à jour `profiles.analyses_count_current_month` (reset automatique si changement de mois UTC).

---

## 3. Endpoints API

### 3.1 Stripe (préfixe `/api/stripe`)

| Méthode | Chemin | Description |
|--------|--------|-------------|
| POST   | `/api/stripe/create-checkout-session` | Crée une session Checkout Stripe |
| POST   | `/api/stripe/create-portal-session`    | Crée une session Customer Portal |
| POST   | `/api/stripe/webhook`                  | Webhook Stripe (événements abonnement) |

#### POST `/api/stripe/create-checkout-session`

**Requête :**
```json
{
  "user_id": "uuid-supabase",
  "price_id": "racer_monthly"
}
```

`price_id` autorisés : `racer_monthly`, `racer_annual`, `team_monthly`, `team_annual`.

**Réponse 200 :**
```json
{
  "checkout_url": "https://checkout.stripe.com/..."
}
```

**Erreurs :**
- 400 `already_subscribed` : l’utilisateur a déjà un abonnement actif (idempotence).
- 400 `invalid_price_id` : `price_id` non reconnu.
- 401 : non utilisé (route publique ; la protection double souscription se fait côté backend via `profiles`).

---

#### POST `/api/stripe/create-portal-session`

**Requête :**
```json
{
  "user_id": "uuid-supabase"
}
```

Le backend récupère `stripe_customer_id` dans `profiles` pour cet utilisateur et crée une session Portal.

**Réponse 200 :**
```json
{
  "portal_url": "https://billing.stripe.com/..."
}
```

**Erreurs :**
- 400 / 404 : pas de `stripe_customer_id` pour cet utilisateur (jamais abonné ou profil absent).

---

#### POST `/api/stripe/webhook`

- Corps : payload brut Stripe.
- Header requis : `Stripe-Signature`.
- Réponse 200 avec `{"received": true}` après traitement réussi.
- En cas d’erreur de signature : 400. En cas d’exception métier : 500 (Stripe retentera).

Événements gérés :
- `checkout.session.completed` : mise à jour `profiles` (stripe_customer_id, stripe_subscription_id, subscription_tier, billing_period, subscription_status, dates).
- `customer.subscription.updated` : synchronisation statut et dates sur `profiles`.
- `customer.subscription.deleted` : passage en `canceled` / fin d’accès (tier selon la logique métier, ex. retour à `rookie`).

---

### 3.2 Utilisateur (préfixe `/api/user`)

#### GET `/api/user/subscription`

**Headers :** `Authorization: Bearer <JWT Supabase>`

**Réponse 200 :**
```json
{
  "tier": "racer",
  "status": "active",
  "billing_period": "monthly",
  "subscription_end_date": "2025-02-15T00:00:00Z",
  "limits": {
    "tier": "racer",
    "analyses_per_month": null,
    "analyses_used": 2,
    "can_export_csv": true,
    "can_export_pdf": false,
    "can_compare": false,
    "max_members": 0,
    "max_circuits": null,
    "max_cars": null
  }
}
```

- `analyses_per_month: null` = illimité. Pour Rookie : `3`.
- Données dérivées de la table `profiles` et de `subscription_service.get_user_limits(user_id)`.

---

## 4. Mapping price_id → tier / billing_period

| price_id       | subscription_tier | billing_period |
|----------------|-------------------|----------------|
| racer_monthly  | racer             | monthly        |
| racer_annual   | racer             | annual         |
| team_monthly   | team              | monthly        |
| team_annual    | team              | annual         |

Les Price IDs réels (Stripe) sont configurés côté backend via variables d’environnement ou une config dédiée (pas en dur dans le code).

---

## 5. Gestion des erreurs et cas limites

- **user_id manquant dans metadata (webhook checkout)** : log warning, réponse 200 pour éviter les retentés Stripe.
- **Signature webhook invalide** : 400, pas de mise à jour en base.
- **Double souscription** : avant création de checkout, le backend vérifie dans `profiles` si l’utilisateur a déjà un abonnement actif ; si oui → 400 `already_subscribed`.
- **Limite d’analyses** : endpoint d’analyse renvoie 403 avec `detail.error = "limit_reached"` et message explicite ; le frontend peut afficher une modal et rediriger vers `/pricing`.
- **JWT manquant ou invalide** sur les routes protégées (`/api/user/subscription`, analyse) : 401.

---

## 6. Variables d’environnement requises

**Backend :**

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Clé secrète Stripe (sk_live_* ou sk_test_*) |
| `STRIPE_WEBHOOK_SECRET` | Secret du webhook (whsec_*) pour vérifier la signature |
| `SUPABASE_URL` | URL du projet Supabase |
| `SUPABASE_SERVICE_KEY` | Clé service_role (accès RLS bypass pour mettre à jour `profiles`) |
| `FRONTEND_URL` | URL du frontend (success_url / cancel_url du Checkout) |

À ne **pas** mettre en dur dans le code : utiliser uniquement des variables d’environnement (ou un secret manager en production).

---

## 7. Sécurité

- **Limites** : vérifiées **côté backend** uniquement (`check_analysis_limit`, `get_user_limits`). Le frontend peut afficher les limites pour l’UX mais ne fait pas autorité.
- **RLS** : activé sur `profiles` et `usage_logs`. Le trigger `protect_profiles_subscription_columns` empêche les utilisateurs authentifiés (role `authenticated`) de modifier les colonnes d’abonnement ; le backend utilise `service_role` pour les mises à jour.
- **usage_logs** : politiques RLS pour que chaque utilisateur ne voie que ses propres lignes.

---

## 8. Tests à effectuer avant déploiement

1. Créer une session checkout avec un `user_id` de test et un `price_id` valide → vérifier la redirection Stripe et que `metadata.user_id` est bien envoyé.
2. Simuler le webhook `checkout.session.completed` (Stripe CLI ou dashboard) → vérifier que **seule** la table `profiles` est mise à jour (pas `user_metadata`).
3. Appeler `GET /api/user/subscription` avec le JWT du même utilisateur → vérifier `tier`, `status`, `limits`.
4. Tester la limite Rookie : 3 analyses puis 403 `limit_reached` et message cohérent.
5. Tester `create-portal-session` avec un utilisateur ayant un `stripe_customer_id` dans `profiles` → redirection vers le portail Stripe.
6. Vérifier que les clés Stripe et Supabase sont lues depuis l’environnement (pas de valeurs par défaut en dur en production).

---

## 9. Fichiers principaux

| Rôle | Fichiers |
|------|----------|
| Backend Stripe | `apexai-backend/src/api/stripe_routes.py` |
| Backend user/subscription | `apexai-backend/src/api/user_routes.py` |
| Service limites | `apexai-backend/src/core/subscription_service.py` |
| Migration DB | `apexai-backend/supabase/migrations/20260102000000_add_profiles_subscription_and_usage_logs.sql` |
| Frontend tarifs | `apex-ai-fresh/src/pages/PricingPage.tsx` |
| Frontend profil | `apex-ai-fresh/src/pages/Profile.tsx` |
| Hook abonnement | `apex-ai-fresh/src/hooks/useSubscription.ts` |
| API client | `apex-ai-fresh/src/lib/api.ts` |
| Upload / limite | `apex-ai-fresh/src/components/upload/CSVUploader.tsx` |

---

*Dernière mise à jour : validation finale du système d’abonnement.*
