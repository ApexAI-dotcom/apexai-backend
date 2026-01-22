# ⚡ Déploiement Express - 5 Minutes

## 🎯 3 Commandes Principales

### 1️⃣ Frontend (Vercel)

```powershell
cd apex-ai-fresh
npm run build
vercel --prod
```

**OU utiliser le script automatique :**

```powershell
.\deploy.ps1
```

### 2️⃣ Backend (Render)

1. Aller sur https://render.com
2. **New** → **Web Service**
3. Connecter repo GitHub
4. Configuration :
   - **Build** : `pip install -r requirements/requirements.txt`
   - **Start** : `python -m uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
   - **Plan** : Free

5. Variables d'environnement (copier-coller) :

```bash
ENVIRONMENT=production
BASE_URL=https://apexai-backend.onrender.com
CORS_ORIGINS=https://apexai.pro,https://www.apexai.pro
STRIPE_SECRET_KEY=sk_test_51SrmwCJY5DvWR2lK8NNjODvfAMcBxOgjGJv2Zz4ruZeGf1cXGEzWgKIlHjzppYbBYzbHW9wLkwI93ZHiX7oNZZaR00TMOYxrZr
STRIPE_WEBHOOK_SECRET=whsec_cf09094bdeb1196ce9dcddde6422618eee77f327c4dcd0fd047e75be794bb493
SUPABASE_URL=https://vlqpljewmujlnxjuqetv.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODkxNzE5MCwiZXhwIjoyMDg0NDkzMTkwfQ.0K3eoXvvyu6Ga3q1NUlKml8QsFduAiA7RNiBEu0s3Us
MOCK_VIDEO_AI=true
```

### 3️⃣ Variables Vercel

Sur https://vercel.com/dashboard → Projet → Settings → Environment Variables :

```
VITE_API_URL=https://apexai-backend.onrender.com
VITE_SUPABASE_URL=https://vlqpljewmujlnxjuqetv.supabase.co
VITE_SUPABASE_ANON_KEY=votre_anon_key_supabase
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_51SrmwCJY5DvWR2lK...
```

**Redéployer** : `vercel --prod`

---

## ✅ Vérification

```powershell
# Backend
curl https://apexai-backend.onrender.com/health

# Frontend
# Ouvrir https://apexai-xxxx.vercel.app
```

---

## 🎉 C'est tout !

**Guide complet** : Voir `DEPLOY.md` pour les détails.
