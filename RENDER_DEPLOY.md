# Déploiement Render.com – Apex AI Backend (10 min)

**Objectif** : Backend live sur `https://apexai-backend.onrender.com` + `/docs` accessible.

---

## Commandes exactes (copier-coller)

```powershell
# 1. Vérifier les fichiers
dir runtime.txt, requirements.txt, render.yaml, Dockerfile, .dockerignore

# 2. Branch deploy + push (si protection)
git checkout -b deploy/render
git add runtime.txt requirements.txt Dockerfile .dockerignore render.yaml docker-compose.yml src run_api.py
git add -u
git commit -m "chore: Render deploy - Python 3.11, runtime.txt, render.yaml"
git push -u origin deploy/render

# 3. Build + Start Render (à saisir dans Dashboard)
# Build:  pip install --upgrade pip && pip install -r requirements.txt
# Start: uvicorn src.api.main:app --host 0.0.0.0 --port $PORT

# 4. Après déploiement
curl -s https://apexai-backend.onrender.com/health
start https://apexai-backend.onrender.com/docs
```

---

## 1. Fichiers à la racine (déjà créés)

| Fichier | Rôle |
|--------|------|
| `runtime.txt` | Force **Python 3.11** (évite 3.13 + pydantic-core Rust) |
| `requirements.txt` | Dépendances pip (pas de Poetry) |
| `Dockerfile` | Fallback Docker si build Render échoue |
| `.dockerignore` | Exclut frontend / node_modules du build |
| `render.yaml` | Config Render zero-config |

---

## 2. Commandes terminal (copier-coller)

### 2.1 Fix GitHub branch protection (push bloqué)

```powershell
# Option A : Désactiver temporairement la protection
# GitHub → Repo → Settings → Branches → Branch protection rules → Edit
# Décocher "Require a pull request before merging" pour main, sauvegarder.
# Push, puis remettre la règle.

# Option B : Push via PR (si protection obligatoire)
git checkout -b deploy/render
git add runtime.txt requirements.txt Dockerfile .dockerignore render.yaml src run_api.py
git add -u
git commit -m "chore: Render deploy - Python 3.11, runtime.txt, render.yaml"
git push -u origin deploy/render
# Puis GitHub → Open PR → Merge dans main.
# Ensuite sur Render : branche = main (ou deploy/render pour tester).
```

### 2.2 Désactiver Poetry (si présent)

```powershell
# Si Render détecte Poetry et échoue :
if (Test-Path pyproject.toml) { Rename-Item pyproject.toml pyproject.toml.bak }
if (Test-Path poetry.lock) { Rename-Item poetry.lock poetry.lock.bak }
git add -A && git commit -m "chore: disable Poetry for Render" && git push
```

### 2.3 Vérifier la structure avant push

```powershell
# Depuis la racine du repo
dir runtime.txt, requirements.txt, render.yaml, Dockerfile, .dockerignore
dir src\api\main.py, run_api.py
```

---

## 3. Render Dashboard – réglages

### 3.1 Créer le Web Service

1. **https://dashboard.render.com** → **New +** → **Web Service**
2. **Connect repository** : `ApexAI-dotcom/apexai-backend` (ou ton repo).
3. Remplir :

| Champ | Valeur |
|-------|--------|
| **Name** | `apexai-backend` |
| **Region** | Frankfurt (ou le plus proche) |
| **Branch** | `main` (ou `deploy/render`) |
| **Root Directory** | *laisser vide* |
| **Runtime** | **Python 3** |
| **Build Command** | `pip install --upgrade pip && pip install -r requirements.txt` |
| **Start Command** | `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT` |

**Structure `backend/src/api/main.py`** (repo apexai-backend) :

- **Root Directory** : `backend`
- **Build Command** : `pip install --upgrade pip && pip install -r requirements.txt`  
  (placer `requirements.txt` dans `backend/` ou à la racine selon ton repo)
- **Start Command** : `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`  
  (exécuté depuis `backend/`, donc module `src.api.main`)

### 3.2 Variables d’environnement (Environment)

Cliquer **Add Environment Variable** et ajouter :

```
ENVIRONMENT       = production
PYTHONUNBUFFERED  = 1
DOCS_ENABLED      = true
PORT              = 8000
```

*(`PORT` est en général fourni par Render ; tu peux ne pas le mettre.)*

**Optionnel** (Stripe, Supabase, etc.) :

```
BASE_URL                  = https://apexai-backend.onrender.com
CORS_ORIGINS              = http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,https://ton-frontend.vercel.app
STRIPE_SECRET_KEY         = sk_test_...
STRIPE_WEBHOOK_SECRET     = whsec_...
SUPABASE_URL              = https://xxx.supabase.co
SUPABASE_SERVICE_KEY      = ...
MOCK_VIDEO_AI             = true
```

**CORS** : pour frontend React en local sur `localhost:3000`, `CORS_ORIGINS` doit contenir `http://localhost:3000` et `http://127.0.0.1:3000`.

### 3.3 Build / Start “bulletproof”

- **Build Command** (recommandé) :
  ```bash
  pip install --upgrade pip && pip install -r requirements.txt
  ```
- **Start Command** (obligatoire) :
  ```bash
  uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
  ```
  Ne pas utiliser de port en dur ; toujours `$PORT`.

### 3.4 Health check

- **Health Check Path** : `/health`

Sauvegarder → **Create Web Service**.

---

## 4. Vérifications après déploiement

### 4.1 Logs Render (extrait type)

Tu devrais voir quelque chose comme :

```
==> Cloning from https://github.com/ApexAI-dotcom/apexai-backend...
==> Using Python version from runtime.txt (python-3.11.9)
==> Installing dependencies with pip
     Collecting fastapi>=0.109.0
     ...
     Successfully installed fastapi uvicorn ...
==> Starting service with 'uvicorn src.api.main:app --host 0.0.0.0 --port $PORT'
     INFO:     Started server process
     INFO:     Uvicorn running on http://0.0.0.0:XXXX
     INFO:     Application startup complete.
```

### 4.2 Tests des endpoints

```powershell
# Health
curl -s https://apexai-backend.onrender.com/health

# Réponse attendue :
# {"status":"healthy","version":"1.0.0","environment":"production"}

# Racine API
curl -s https://apexai-backend.onrender.com/

# Docs Swagger (si DOCS_ENABLED=true)
start https://apexai-backend.onrender.com/docs
```

### 4.3 CORS (frontend React `localhost:3000`)

Depuis ton app React sur `http://localhost:3000` :

```js
fetch('https://apexai-backend.onrender.com/health')
  .then(r => r.json())
  .then(console.log);
```

Pas d’erreur CORS si `CORS_ORIGINS` contient `http://localhost:3000` et `http://127.0.0.1:3000`.

---

## 5. Fallbacks si Render échoue

### 5.1 Railway.app

1. **https://railway.app** → **New Project** → **Deploy from GitHub** → `apexai-backend`.
2. **Settings** :
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
   - **Root Directory** : vide (ou `backend` si structure `backend/src/...`).
3. **Variables** : mêmes que Render (`ENVIRONMENT`, `DOCS_ENABLED`, `CORS_ORIGINS`, etc.).
4. **Generate Domain** → utiliser l’URL fournie (ex. `https://apexai-backend.up.railway.app`).

### 5.2 Docker Compose local + ngrok

```powershell
# À la racine du repo
docker build -t apexai-backend .
docker run -p 8000:8000 -e ENVIRONMENT=production -e DOCS_ENABLED=true apexai-backend
```

Puis :

```powershell
ngrok http 8000
# Utiliser l’URL https générée pour exposer le backend.
```

Exemple `docker-compose.yml` à la racine :

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DOCS_ENABLED=true
      - CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

```powershell
docker compose up --build
```

---

## 6. Récap

| Étape | Action |
|-------|--------|
| 1 | `runtime.txt` (3.11), `requirements.txt`, `render.yaml`, `Dockerfile`, `.dockerignore` à la racine |
| 2 | Corriger branch protection ou push via branche `deploy/render` + PR |
| 3 | Désactiver Poetry si présent (`pyproject.toml` / `poetry.lock` renommés) |
| 4 | Render : Web Service, Build = `pip install...`, Start = `uvicorn ... --port $PORT` |
| 5 | Env : `ENVIRONMENT`, `DOCS_ENABLED`, `CORS_ORIGINS` (avec `localhost:3000`) |
| 6 | Vérifier `/health` et `/docs` |

**URL cible** : `https://apexai-backend.onrender.com/docs` → backend live.
