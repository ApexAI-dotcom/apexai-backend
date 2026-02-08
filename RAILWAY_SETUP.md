# Configuration Railway – Apex AI Backend

## Problème

Railway détecte `package.json` à la racine du repo → environnement **Node.js** → `pip` non disponible.

## Solution : Root Directory

Dans le **Railway Dashboard** :

1. Ouvrir le service **apexai-backend**
2. Aller dans **Settings** → **Source**
3. **Root Directory** : `apexai-backend`
4. Redéployer (Deploy → Redeploy)

Avec `apexai-backend` comme racine, Railway ne voit plus `package.json` et détecte `requirements.txt` → build Python.

## Commandes Build/Start (si besoin)

Si les commandes ne sont pas détectées automatiquement :

- **Build Command** : `pip install -r requirements.txt`
- **Start Command** : `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`

Ou laisser le **Builder** sur **Railpack** (auto-détection Python).

## Alternative : Dockerfile

Si Railpack pose problème, utiliser le Dockerfile :

1. **Settings** → **Build** → **Builder** : **Dockerfile**
2. **Dockerfile Path** : `apexai-backend/Dockerfile`
3. **Root Directory** : `apexai-backend`
