# Déploiement Vercel

Ce dossier est le **frontend** du projet. Le dépôt contient aussi le backend (à la racine).

## Configuration Vercel

1. Connecte le projet GitHub **ApexAI-dotcom/apexai-backend** (ou ton repo) à Vercel.
2. **Root Directory** : indique `apex-ai-fresh` (Vercel buildra uniquement ce dossier).
3. **Build Command** : `npm run build` (déjà dans `vercel.json`).
4. **Output Directory** : `dist` (déjà dans `vercel.json`).
5. Variables d'environnement à définir dans Vercel (Settings → Environment Variables) :
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`
   - `VITE_API_URL` (URL de ton backend en prod)

Chaque push sur `master` déclenchera un déploiement automatique.
