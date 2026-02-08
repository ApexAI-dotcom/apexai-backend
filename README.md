# Apex AI – Analyse de télémétrie karting

Système d'analyse de télémétrie karting avec scoring IA et coaching personnalisé.

## Démarrage rapide

### Backend

```bash
cd apexai-backend
pip install -r requirements.txt
python run_api.py
```

API : http://localhost:8000 | Docs : http://localhost:8000/docs

### Frontend

```bash
cd apex-ai-fresh
npm install
npm run dev
```

App : http://localhost:5173

## Structure

- `apexai-backend/` – API FastAPI (analyse CSV, Stripe, Supabase)
- `apex-ai-fresh/` – Frontend React (Vite, Shadcn UI)

## Déploiement

- **Frontend** : Vercel (`apex-ai-fresh`)
- **Backend** : Railway (`apexai-backend`)

Voir `DEPLOY.md` et `QUICK_DEPLOY.md` pour les instructions.

## Services

| Service   | Usage       |
|----------|-------------|
| Stripe   | Paiements   |
| Supabase | Authentification |
