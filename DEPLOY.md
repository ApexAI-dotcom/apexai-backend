# 🚀 Guide de Déploiement PROD - ApexAI

Guide complet pour déployer ApexAI en production en 15 minutes !

## 📋 Prérequis

- Compte GitHub avec le repo ApexAI
- Compte Vercel (gratuit) : https://vercel.com
- Compte Render (gratuit) : https://render.com
- Domaine `apexai.pro` (optionnel mais recommandé)

---

## 🎯 ÉTAPE 1: BUILD Frontend (2min)

```powershell
cd apex-ai-fresh
npm run build
```

✅ Le dossier `dist/` est créé avec les assets optimisés.

---

## 🌐 ÉTAPE 2: Vercel - Frontend (5min)

### 2.1 Installation Vercel CLI

```powershell
npm i -g vercel
```

### 2.2 Login Vercel

```powershell
vercel login
```

Suivez les instructions dans le navigateur.

### 2.3 Déploiement

```powershell
cd apex-ai-fresh
vercel --prod
```

**Réponses aux questions :**
- **Link to existing project?** → `N` (première fois) ou `Y` (mises à jour)
- **Project name?** → `apexai` ou `apex-ai`
- **Directory?** → `./` (ou laisser par défaut)
- **Override settings?** → `N`

✅ Vercel génère une URL : `https://apexai-xxxx.vercel.app`

### 2.4 Configuration Domaine (Optionnel)

1. Aller sur https://vercel.com/dashboard
2. Sélectionner le projet `apexai`
3. **Settings** → **Domains**
4. Ajouter `apexai.pro` et `www.apexai.pro`
5. Configurer DNS :

```
Type: CNAME
Name: apexai (ou @)
Value: cname.vercel-dns.com
TTL: 3600
```

### 2.5 Variables d'Environnement Vercel

Dans **Settings** → **Environment Variables**, ajouter :

```
VITE_API_URL=https://apexai-backend.onrender.com
VITE_SUPABASE_URL=https://vlqpljewmujlnxjuqetv.supabase.co
VITE_SUPABASE_ANON_KEY=votre_anon_key_supabase
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_51SrmwCJY5DvWR2lK...
```

⚠️ **Important** : Après ajout des variables, **redéployer** :

```powershell
vercel --prod
```

---

## ⚙️ ÉTAPE 3: Render - Backend (5min)

### 3.1 Créer le Service

1. Aller sur https://render.com
2. **New** → **Web Service**
3. Connecter le repo GitHub `ApexAI`
4. Configuration :

   - **Name** : `apexai-backend`
   - **Region** : `Frankfurt` (ou plus proche)
   - **Branch** : `main` (ou `master`)
   - **Root Directory** : `/` (laisser vide)
   - **Runtime** : `Python 3`
   - **Build Command** : `pip install -r requirements/requirements.txt`
   - **Start Command** : `python -m uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type** : `Free` (ou `Starter` pour plus de RAM)

### 3.2 Variables d'Environnement Render

Dans **Environment**, ajouter :

```bash
ENVIRONMENT=production
BASE_URL=https://apexai-backend.onrender.com
CORS_ORIGINS=https://apexai.pro,https://www.apexai.pro,https://apexai-xxxx.vercel.app
PYTHONUNBUFFERED=1
STRIPE_SECRET_KEY=sk_test_51SrmwCJY5DvWR2lK8NNjODvfAMcBxOgjGJv2Zz4ruZeGf1cXGEzWgKIlHjzppYbBYzbHW9wLkwI93ZHiX7oNZZaR00TMOYxrZr
STRIPE_WEBHOOK_SECRET=whsec_cf09094bdeb1196ce9dcddde6422618eee77f327c4dcd0fd047e75be794bb493
SUPABASE_URL=https://vlqpljewmujlnxjuqetv.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODkxNzE5MCwiZXhwIjoyMDg0NDkzMTkwfQ.0K3eoXvvyu6Ga3q1NUlKml8QsFduAiA7RNiBEu0s3Us
MOCK_VIDEO_AI=true
```

### 3.3 Déployer

Cliquer sur **Create Web Service**

⏱️ Premier déploiement : ~5-10 minutes

✅ URL générée : `https://apexai-backend.onrender.com`

### 3.4 Webhook Stripe (Important)

1. Dans Render, copier l'URL : `https://apexai-backend.onrender.com`
2. Aller sur https://dashboard.stripe.com/webhooks
3. **Add endpoint**
4. **Endpoint URL** : `https://apexai-backend.onrender.com/api/webhook/stripe`
5. **Events to send** : `checkout.session.completed`
6. Copier le **Signing secret** (`whsec_...`)
7. Mettre à jour `STRIPE_WEBHOOK_SECRET` dans Render

---

## ✅ ÉTAPE 4: Vérification Finale

### 4.1 Backend Health Check

```powershell
curl https://apexai-backend.onrender.com/health
```

Réponse attendue :
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production"
}
```

### 4.2 Frontend

Ouvrir https://apexai.pro (ou l'URL Vercel)

✅ Vérifier :
- Page d'accueil charge
- Bouton "Upload CSV" fonctionne
- Dashboard accessible
- Pricing page affichée

### 4.3 Test Stripe

1. Aller sur `/pricing`
2. Cliquer sur **"Essai 14 jours"** (Plan Pro)
3. Utiliser carte de test : `4242 4242 4242 4242`
4. Vérifier redirection après paiement

---

## 🎉 RÉSULTAT FINAL

```
✅ Frontend: https://apexai.pro
✅ Backend:  https://apexai-backend.onrender.com
✅ Stripe:   Actif (webhook configuré)
✅ Supabase: Connecté
```

---

## 🐛 Dépannage

### Backend ne démarre pas

- Vérifier les logs Render
- Vérifier `requirements/requirements.txt` existe
- Vérifier `startCommand` est correct

### CORS Error

- Ajouter l'URL Vercel dans `CORS_ORIGINS` Render
- Redéployer le backend

### Variables d'env non prises en compte

- **Vercel** : Redéployer après ajout
- **Render** : Service redémarre automatiquement

### 404 sur `/api/*`

- Vérifier `BASE_URL` dans Vercel pointe vers Render
- Vérifier backend est accessible : `/health`

---

## 💰 Coûts

| Service | Plan | Coût |
|---------|------|------|
| Vercel | Free | **$0/mois** |
| Render | Free | **$0/mois** (limite 750h) |
| Supabase | Free | **$0/mois** |
| Stripe | Pay-as-you-go | **0% commission** |

**Total : $0/mois** (tant que trafic < limites gratuites)

---

## 🚀 Commandes Rapides

```powershell
# Frontend - Build & Deploy
cd apex-ai-fresh
npm run build
vercel --prod

# Backend - Logs Render
# Aller sur dashboard.render.com → Logs

# Health Check
curl https://apexai-backend.onrender.com/health
```

---

## 📝 Notes

- Render Free peut mettre le service en veille après 15min d'inactivité
- Premier réveil peut prendre ~30 secondes
- Pour éviter ça, passer à **Starter** ($7/mois) ou utiliser un service de ping
- Vercel CDN cache les assets automatiquement

---

**🎯 Déploiement réussi ! ApexAI est maintenant en production !**
