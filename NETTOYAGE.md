# Nettoyage du projet Apex AI

Résumé des suppressions et mises à jour effectuées.

## Supprimé

### Telegram
- `telegram_bot/` (dossier entier)
- `run_bot.py`
- `requirements/requirements_bot.txt`
- `.gitignore_bot`
- Références dans `env.example`, `docs/env.example`

### Render
- `render.yaml`
- `RENDER_DEPLOY.md`

### Doublons et obsolètes
- `src/` à la racine (code dans `apexai-backend/src/`)
- `tests/` à la racine (tests dans `apexai-backend/tests/`)
- `backend/` (ancien backend Lovable)
- `requirements/` (dépendances dans `apexai-backend/`)
- `requirements.txt`, `requirements_api.txt`, `runtime.txt` à la racine
- `cleanup_project.py`

## Conservé

- **apexai-backend/** : Backend FastAPI
- **apex-ai-fresh/** : Frontend React
- **Stripe** : Intégration paiements
- **Supabase** : Auth
- **Vercel** : Déploiement frontend
- **Railway** : Déploiement backend

## Configurations mises à jour

- `env.example` : Stripe, Supabase (sans Telegram)
- `docs/env.example` : Exemple générique
- `DEPLOY.md` : Railway au lieu de Render
- `QUICK_DEPLOY.md` : Railway
- `deploy.ps1` : Référence Railway
- `PROJECT_STRUCTURE.md` : Structure actuelle
- `README.md` : Instructions à jour
- `.dockerignore` : Suppression référence render.yaml
