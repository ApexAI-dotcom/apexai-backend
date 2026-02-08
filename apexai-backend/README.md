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

## Démarrage local

```bash
cd apexai-backend
pip install -r requirements.txt
python run_api.py
```

API disponible sur http://localhost:8000

## Endpoints principaux

- `POST /api/v1/analyze` - Analyse CSV télémétrie
- `POST /api/create-checkout-session` - Stripe Checkout
- `POST /api/webhook/stripe` - Webhook Stripe
- `GET /api/subscription-status` - Statut abonnement
- `GET /health` - Health check
