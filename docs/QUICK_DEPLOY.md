# Déploiement rapide – ApexAI

## Frontend (Vercel)

```powershell
cd apex-ai-fresh
npm run build
vercel --prod
```

Ou : `.\deploy.ps1`

## Backend (Railway)

1. https://railway.app → **New Project** → **Deploy from GitHub**
2. Repo : ApexAI
3. **Root Directory** : `apexai-backend`
4. **Start Command** : `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
5. Ajouter les variables d'environnement (voir `DEPLOY.md`)

## Variables Vercel

```
VITE_API_URL=https://votre-backend.railway.app
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
VITE_STRIPE_PUBLISHABLE_KEY=...
```

Voir `DEPLOY.md` pour le détail.
