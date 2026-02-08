# Guide de déploiement – ApexAI

Guide pour déployer ApexAI en production (Railway + Vercel).

## Prérequis

- Compte GitHub avec le repo ApexAI
- Compte Vercel : https://vercel.com
- Compte Railway : https://railway.app
- Domaine (optionnel)

---

## Étape 1 : Frontend (Vercel)

```powershell
cd apex-ai-fresh
npm run build
vercel --prod
```

### Variables d'environnement Vercel

Dans **Settings** → **Environment Variables** :

```
VITE_API_URL=https://votre-backend.railway.app
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=votre_anon_key
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_...
```

---

## Étape 2 : Backend (Railway)

1. https://railway.app → **New Project** → **Deploy from GitHub**
2. Sélectionner le repo ApexAI
3. Configuration :
   - **Root Directory** : `apexai-backend`
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`

### Variables d'environnement Railway

```
ENVIRONMENT=production
BASE_URL=https://votre-backend.railway.app
CORS_ORIGINS=https://votre-site.vercel.app,https://apexai.pro
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=...
MOCK_VIDEO_AI=true
```

### Webhook Stripe

1. URL du backend : `https://votre-backend.railway.app`
2. Stripe Dashboard → Webhooks → **Add endpoint**
3. URL : `https://votre-backend.railway.app/api/webhook/stripe`
4. Event : `checkout.session.completed`
5. Copier le **Signing secret** dans `STRIPE_WEBHOOK_SECRET`

---

## Vérification

```powershell
curl https://votre-backend.railway.app/health
```

Réponse attendue : `{"status":"healthy",...}`

---

## Services utilisés

| Service   | Rôle           |
|----------|-----------------|
| Vercel   | Frontend React  |
| Railway  | Backend FastAPI |
| Stripe   | Paiements       |
| Supabase | Auth            |
