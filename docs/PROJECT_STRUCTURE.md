# Structure du projet Apex AI

## Structure globale

```
ApexAI/
├── apexai-backend/        # Backend FastAPI
│   ├── src/
│   │   ├── api/           # main.py, routes.py, services.py, stripe_routes.py...
│   │   ├── core/          # data_loader, signal_processing
│   │   ├── analysis/      # geometry, scoring, coaching
│   │   └── visualization/
│   ├── tests/
│   ├── run_api.py
│   ├── requirements.txt
│   ├── runtime.txt
│   ├── Dockerfile
│   └── env.example
│
├── apex-ai-fresh/         # Frontend React (Vite, Shadcn)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── lib/
│   │   └── hooks/
│   ├── public/
│   └── package.json
│
├── docs/
├── scripts/
├── data/
├── logs/
├── run_api.py             # Délègue vers apexai-backend
├── start_backend.bat
├── start_backend.sh
├── start_frontend.bat
├── start_frontend.sh
├── deploy.ps1
├── docker-compose.yml
├── env.example
├── DEPLOY.md
├── QUICK_DEPLOY.md
└── REORGANISATION_BACKEND.md
```

## Démarrage local

**Backend :**
```bash
cd apexai-backend
pip install -r requirements.txt
python run_api.py
# ou depuis racine : python run_api.py
```

**Frontend :**
```bash
cd apex-ai-fresh
npm install
npm run dev
```

## Services

| Service   | Usage          |
|----------|----------------|
| Vercel   | Frontend       |
| Railway  | Backend        |
| Stripe   | Paiements      |
| Supabase | Auth           |
