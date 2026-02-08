# Réorganisation du Backend Apex AI

## Nouvelle structure

Le backend a été déplacé dans le dossier `apexai-backend/` :

```
ApexAI/
├── apexai-backend/          ← NOUVEAU : Backend API
│   ├── src/
│   │   ├── api/             # main.py, routes.py, services.py, stripe_routes.py...
│   │   ├── core/            # data_loader, signal_processing
│   │   ├── analysis/        # geometry, scoring, coaching
│   │   └── visualization/   # graphiques Matplotlib
│   ├── tests/
│   ├── run_api.py
│   ├── requirements.txt
│   ├── runtime.txt
│   ├── Dockerfile
│   └── env.example
├── apex-ai-fresh/           # Frontend (inchangé)
└── ...
```

## Démarrage local

**Option 1 - Depuis apexai-backend :**
```bash
cd apexai-backend
pip install -r requirements.txt
python run_api.py
```

**Option 2 - Depuis la racine :**
```bash
python run_api.py    # Délègue vers apexai-backend
```

**Option 3 - Scripts :**
```bash
./start_backend.bat   # Windows
./start_backend.sh    # Linux/Mac
```

## Déploiement

### Railway
Dans le dashboard Railway :
- **Root Directory** : `apexai-backend`
- **Start Command** : `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`

### Docker
```bash
docker build -t apexai-backend ./apexai-backend
docker run -p 8000:8000 apexai-backend
```

Ou via docker-compose (depuis la racine) :
```bash
docker compose up --build
```

## Configurations inchangées

- **Vercel** : Déploie `apex-ai-fresh/` (frontend) - pas de modification
- **Stripe** : Clés dans variables d'environnement (STRIPE_SECRET_KEY, etc.)
- **Supabase** : Clés dans variables d'environnement (SUPABASE_URL, etc.)
- **Variables d'env** : À configurer dans Railway
