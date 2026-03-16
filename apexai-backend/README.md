# Apex AI Backend

API REST FastAPI pour l'analyse de télémétrie karting.

## Structure

```
apexai-backend/
├── src/
│   ├── api/        # Routes, services, config
│   ├── core/       # Data loader, signal processing
│   ├── analysis/   # Geometry, scoring, coaching
│   └── visualization/  # Graphiques Matplotlib
├── tests/
├── run_api.py
├── requirements.txt
└── runtime.txt
```

## Démarrage local (développement)

```bash
cd apexai-backend
pip install -r requirements.txt
python run_api.py
```

API disponible sur http://localhost:8000

En production, le backend est déployé sur Railway à partir de la branche `master` de ce dépôt.

## Endpoints principaux

- `POST /api/v1/analyze` - Analyse CSV télémétrie
- `POST /api/create-checkout-session` - Stripe Checkout
- `POST /api/webhook/stripe` - Webhook Stripe
- `GET /api/user/subscription` - Statut abonnement (Bearer JWT ou user_id en query/X-User-Id)
- `GET /health` - Health check
