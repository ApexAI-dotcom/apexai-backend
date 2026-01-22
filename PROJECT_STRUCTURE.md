# 📁 Structure du Projet Apex AI

Structure complète et organisée du projet Apex AI - Analyse de Télémétrie Karting avec IA.

---

## 🏗️ Structure Globale

```
ApexAI/
├── apex-ai-fresh/          # Frontend React/TypeScript (Vite)
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                # Backend simple (Lovable)
│   ├── main.py
│   └── requirements.txt
│
├── src/                    # Backend complet (FastAPI)
│   ├── api/               # API REST
│   ├── core/              # Pipeline de traitement
│   ├── analysis/          # Analyse et scoring
│   └── visualization/     # Génération graphiques
│
├── requirements/           # Dépendances Python
├── telegram_bot/          # Bot Telegram
├── tests/                 # Tests Python
├── docs/                  # Documentation
├── scripts/               # Scripts utilitaires
├── output/                # Graphiques générés
└── temp/                  # Fichiers temporaires
```

---

## 📂 Frontend (`apex-ai-fresh/`)

### Structure Complète

```
apex-ai-fresh/
├── public/
│   ├── favicon.ico
│   ├── placeholder.svg
│   └── robots.txt
│
├── src/
│   ├── app/                    # Routes + Layouts (à créer)
│   │   └── (future structure)
│   │
│   ├── components/             # Composants React
│   │   ├── ui/                # Shadcn UI Components (49 fichiers)
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── table.tsx
│   │   │   └── ... (45 autres)
│   │   │
│   │   ├── layout/            # Layout Components
│   │   │   ├── Layout.tsx
│   │   │   ├── Navbar.tsx
│   │   │   └── MobileNav.tsx
│   │   │
│   │   ├── stats/             # Statistiques
│   │   │   ├── ScoreCard.tsx
│   │   │   └── StatCard.tsx
│   │   │
│   │   ├── racing/            # Composants Racing
│   │   │   └── ApexGraph.tsx
│   │   │
│   │   ├── pricing/           # Pricing
│   │   │   └── PricingCard.tsx
│   │   │
│   │   ├── upload/            # Upload
│   │   │   └── CSVUploader.tsx
│   │   │
│   │   └── NavLink.tsx        # Navigation Link
│   │
│   ├── pages/                  # Pages de l'application
│   │   ├── Index.tsx          # Page d'accueil
│   │   ├── Upload.tsx         # Upload CSV
│   │   ├── Dashboard.tsx     # Dashboard analyses
│   │   ├── Pricing.tsx       # Tarifs
│   │   ├── Profile.tsx       # Profil utilisateur
│   │   └── NotFound.tsx      # Page 404
│   │
│   ├── lib/                    # Utilitaires et API
│   │   ├── api.ts            # Client API Backend
│   │   ├── storage.ts        # Système de stockage local
│   │   └── utils.ts          # Utilitaires généraux
│   │
│   ├── hooks/                  # Hooks React personnalisés
│   │   ├── use-mobile.tsx
│   │   └── use-toast.ts
│   │
│   ├── assets/                 # Ressources statiques
│   │   └── hero-racing.jpg
│   │
│   ├── test/                   # Tests
│   │   ├── example.test.ts
│   │   └── setup.ts
│   │
│   ├── App.tsx                 # Composant principal + Router
│   ├── App.css                 # Styles App
│   ├── main.tsx                # Point d'entrée React
│   ├── index.css               # Styles globaux Tailwind
│   └── vite-env.d.ts          # Types Vite
│
├── .env.example                # Exemple variables d'environnement
├── .gitignore                  # Git ignore
├── .prettierrc                 # Configuration Prettier
├── .prettierignore             # Prettier ignore
├── components.json              # Configuration Shadcn UI
├── eslint.config.js            # Configuration ESLint
├── index.html                  # HTML principal
├── package.json                # Dépendances npm
├── postcss.config.js           # Configuration PostCSS
├── tailwind.config.ts          # Configuration Tailwind
├── tsconfig.json               # Configuration TypeScript
├── tsconfig.app.json           # TS config app
├── tsconfig.node.json          # TS config node
├── vite.config.ts              # Configuration Vite
├── vitest.config.ts            # Configuration Vitest
└── README.md                   # Documentation frontend
```

---

## 🐍 Backend (`src/`)

### Structure Complète

```
src/
├── api/                        # API REST FastAPI
│   ├── __init__.py
│   ├── main.py                # Application FastAPI
│   ├── routes.py              # Endpoints API
│   ├── services.py            # Logique métier
│   ├── models.py              # Modèles Pydantic
│   ├── config.py              # Configuration
│   └── utils.py               # Utilitaires API
│
├── core/                       # Pipeline de traitement
│   ├── data_loader.py         # Chargement CSV robuste
│   └── signal_processing.py   # Filtrage Savitzky-Golay
│
├── analysis/                   # Analyse et scoring
│   ├── geometry.py            # Géométrie trajectoire
│   ├── scoring.py             # Système de scoring /100
│   ├── coaching.py            # Génération conseils IA
│   └── performance_metrics.py # Métriques détaillées
│
├── visualization/              # Génération graphiques
│   └── visualization.py       # 10 graphiques F1-style
│
├── coaching/                   # (vide, pour extensions futures)
└── interfaces/                 # (vide, pour extensions futures)
```

---

## 📋 Fichiers Racine Importants

### Documentation

- `README.md` - Documentation principale
- `PROJECT_STRUCTURE.md` - Ce fichier
- `BACKEND_STARTUP.md` - Guide démarrage backend
- `README_API.md` - Documentation API REST
- `CURSOR_MIGRATION.md` - Guide migration Lovable → Cursor
- `INTEGRATION_GUIDE.md` - Guide intégration backend/frontend

### Configuration

- `requirements_api.txt` - Dépendances API FastAPI
- `requirements/requirements.txt` - Dépendances pipeline Python
- `run_api.py` - Script lancement API
- `Dockerfile` - Containerisation API
- `render.yaml` - Configuration déploiement Render

### Scripts

- `start_backend.sh` / `.bat` - Démarrage backend
- `start_frontend.sh` / `.bat` - Démarrage frontend
- `cleanup_project.py` - Script nettoyage projet

---

## 🚀 Guide de Démarrage

### Frontend

```bash
cd apex-ai-fresh
npm install
cp .env.example .env
npm run dev
```

**URL** : http://localhost:8080

### Backend Complet

```bash
# Créer environnement virtuel
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Installer dépendances
pip install -r requirements/requirements.txt -r requirements_api.txt

# Démarrer API
python run_api.py
# OU
uvicorn src.api.main:app --reload
```

**URL** : http://localhost:8000  
**Docs** : http://localhost:8000/docs

### Backend Simple (Lovable)

```bash
cd backend
pip install -r requirements.txt
python main.py
```

**URL** : http://localhost:8000

---

## 📦 Dépendances Principales

### Frontend (`apex-ai-fresh/package.json`)

**Core:**
- `react` ^18.3.1
- `react-dom` ^18.3.1
- `react-router-dom` ^6.30.1

**UI:**
- `@radix-ui/*` - Composants UI accessibles
- `tailwindcss` ^3.4.17
- `lucide-react` ^0.462.0
- `framer-motion` ^12.26.2

**State & Data:**
- `@tanstack/react-query` ^5.83.0
- `react-hook-form` ^7.61.1
- `zod` ^3.25.76

**Dev:**
- `vite` ^5.4.19
- `typescript` ^5.8.3
- `eslint` ^9.32.0
- `prettier` ^3.4.2
- `vitest` ^3.2.4

### Backend (`requirements_api.txt`)

- `fastapi` ^0.109.0
- `uvicorn[standard]` ^0.27.0
- `pydantic` ^2.5.3
- `pandas` >=2.0.0
- `numpy` >=1.24.0
- `scipy` >=1.11.0
- `matplotlib` >=3.7.0

---

## 🔧 Configuration

### Variables d'Environnement

**Frontend (`.env`):**
```env
VITE_API_URL=http://localhost:8000
```

**Backend (optionnel):**
```env
ENVIRONMENT=development
BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:8080,http://localhost:3000
```

### Ports

- **Frontend** : 8080 (configuré dans `vite.config.ts`)
- **Backend API** : 8000 (configuré dans `run_api.py`)

---

## 📡 Endpoints API

### Backend Complet (`/src/api/`)

- `GET /` - Informations API
- `GET /health` - Health check
- `POST /api/v1/analyze` - Analyser CSV
- `GET /api/v1/status/{id}` - Statut analyse
- `GET /output/{id}/{plot}.png` - Graphiques générés

### Backend Simple (`/backend/`)

- `POST /api/upload` - Upload CSV (format Lovable)

---

## 🧪 Tests

### Frontend

```bash
npm run test          # Tests unitaires
npm run test:watch    # Mode watch
npm run test:ui       # Interface UI
```

### Backend

```bash
# Tests Python (à implémenter)
pytest tests/
```

---

## 📝 Scripts Disponibles

### Frontend

```bash
npm run dev           # Développement
npm run build         # Build production
npm run preview       # Preview build
npm run lint          # Linter + fix
npm run lint:check    # Linter check only
npm run format        # Formatter code
npm run format:check  # Format check only
npm run type-check    # Vérification TypeScript
npm test              # Tests
```

### Backend

```bash
python run_api.py                    # Démarrer API
uvicorn src.api.main:app --reload    # Démarrer avec reload
```

---

## 🗂️ Organisation des Fichiers

### Composants UI (`src/components/ui/`)

Tous les composants Shadcn UI sont dans ce dossier. Ajouter de nouveaux composants via :

```bash
npx shadcn-ui@latest add [component-name]
```

### Pages (`src/pages/`)

Chaque page correspond à une route dans `App.tsx` :
- `/` → `Index.tsx`
- `/upload` → `Upload.tsx`
- `/dashboard` → `Dashboard.tsx`
- `/pricing` → `Pricing.tsx`
- `/profile` → `Profile.tsx`
- `/*` → `NotFound.tsx`

### Utilitaires (`src/lib/`)

- `api.ts` - Client API pour communiquer avec le backend
- `storage.ts` - Système de stockage local (localStorage)
- `utils.ts` - Fonctions utilitaires (cn, etc.)

---

## 🚢 Déploiement

### Frontend (Vercel/Netlify)

```bash
npm run build
# Déployer le dossier dist/
```

### Backend (Render/Railway)

```bash
# Utiliser Dockerfile ou render.yaml
docker build -t apex-ai-api .
docker run -p 8000:8000 apex-ai-api
```

---

## 📚 Documentation Complémentaire

- **Backend** : `BACKEND_STARTUP.md`
- **API** : `README_API.md`
- **Migration** : `CURSOR_MIGRATION.md`
- **Intégration** : `INTEGRATION_GUIDE.md`

---

## ✅ Checklist Production

- [x] Structure organisée
- [x] Configuration ESLint + Prettier
- [x] Variables d'environnement documentées
- [x] Scripts npm configurés
- [x] Documentation complète
- [x] Tests configurés
- [x] Build production fonctionnel
- [x] Backend API opérationnel
- [x] Frontend connecté au backend
- [x] Stockage local implémenté

---

**Dernière mise à jour** : 2024-01-20  
**Version** : 1.0.0
