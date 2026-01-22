# 🏎️ APEX AI - Analyse de Télémétrie Karting avec IA

Système complet d'analyse de télémétrie karting avec intelligence artificielle pour améliorer les performances sur circuit.

## 🚀 Démarrage Rapide

### Prérequis

- **Python 3.11+**
- **Node.js 18+**
- **npm** ou **yarn**

### Installation

#### 1. Backend (FastAPI)

```bash
# Installer les dépendances Python
cd backend
pip install -r requirements.txt

# Lancer le serveur
python main.py
# OU
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Le backend sera disponible sur : **http://localhost:8000**

#### 2. Frontend (React + Vite)

```bash
# Installer les dépendances
cd lovable-app
npm install

# Lancer le serveur de développement
npm run dev
```

Le frontend sera disponible sur : **http://localhost:3000**

## 📁 Structure du Projet

```
ApexAI/
├── backend/                 # API FastAPI
│   ├── main.py             # Point d'entrée FastAPI
│   └── requirements.txt    # Dépendances Python
│
├── lovable-app/            # Application React
│   ├── src/
│   │   ├── pages/          # Pages de l'application
│   │   │   ├── index.tsx   # Page d'accueil
│   │   │   ├── UploadPage.tsx  # Upload CSV
│   │   │   ├── Dashboard.tsx   # Tableau de bord
│   │   │   ├── Pricing.tsx     # Tarifs
│   │   │   ├── Profile.tsx     # Profil utilisateur
│   │   │   └── NotFound.tsx     # Page 404
│   │   ├── components/     # Composants React
│   │   │   ├── ui/         # Composants Shadcn UI
│   │   │   ├── layout/     # Layout et navigation
│   │   │   ├── stats/      # Composants statistiques
│   │   │   └── racing/     # Composants karting
│   │   ├── lib/            # Utilitaires
│   │   │   ├── api.ts      # Client API
│   │   │   └── utils.ts    # Fonctions utilitaires
│   │   └── assets/         # Images et ressources
│   └── package.json
│
└── README.md               # Ce fichier
```

## 🎯 Fonctionnalités

### Backend

- ✅ **API REST FastAPI** : Analyse de fichiers CSV MyChron
- ✅ **Endpoint** : `POST /api/upload` pour upload et analyse
- ✅ **Métriques calculées** : CBV, Chroma, Trajectoire, Vitesse
- ✅ **Score de performance** : Calcul automatique /100

### Frontend

- ✅ **Page d'accueil** : Hero section avec présentation
- ✅ **Upload CSV** : Drag & drop avec preview
- ✅ **Dashboard** : Visualisation des statistiques
- ✅ **Pricing** : Page tarifs
- ✅ **Profile** : Profil utilisateur
- ✅ **Design Purple** : Glassmorphism moderne

## 🔌 API Endpoints

### POST /api/upload

Upload un fichier CSV MyChron et reçoit une analyse complète.

**Request** :
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@telemetry.csv"
```

**Response** :
```json
{
  "success": true,
  "score": 87,
  "status": "moyenne",
  "analyses": {
    "CBV": "Haute",
    "Chroma": "Bonne",
    "Trajectoire": "Optimale",
    "Vitesse": "Régulière"
  },
  "extract": "3.2s"
}
```

## 🎨 Design

- **Thème** : Purple glassmorphism
- **Framework CSS** : Tailwind CSS v3
- **Composants UI** : Shadcn UI
- **Animations** : Framer Motion
- **Icons** : Lucide React

## 📦 Dépendances Principales

### Backend

- `fastapi` : Framework web
- `uvicorn` : Serveur ASGI
- `pandas` : Manipulation de données CSV
- `numpy` : Calculs numériques

### Frontend

- `react` : Framework UI
- `react-router-dom` : Routing
- `tailwindcss` : CSS framework
- `framer-motion` : Animations
- `lucide-react` : Icons
- `sonner` : Notifications toast

## 🧪 Tests

### Tester le Backend

```bash
cd backend
python main.py
# Ouvrir http://localhost:8000/docs pour la documentation Swagger
```

### Tester le Frontend

```bash
cd lovable-app
npm run dev
# Ouvrir http://localhost:3000
```

### Tester l'Upload CSV

1. Aller sur **http://localhost:3000/upload**
2. Glisser-déposer un fichier CSV MyChron
3. Voir le preview des données
4. Cliquer sur "Analyser le fichier"
5. Voir les résultats avec score et métriques

## 🛠️ Build Production

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd lovable-app
npm run build
# Les fichiers seront dans dist/
npm run preview  # Pour tester le build
```

## 📝 Routes Disponibles

- `/` - Page d'accueil
- `/upload` - Upload CSV MyChron
- `/dashboard` - Tableau de bord
- `/pricing` - Tarifs
- `/profile` - Profil utilisateur
- `/*` - Page 404 (NotFound)

## 🔧 Configuration

### Variables d'environnement

Créer un fichier `.env` dans `lovable-app/` :

```env
VITE_API_URL=http://localhost:8000
```

### Backend Configuration

Le backend écoute par défaut sur `http://localhost:8000`.

Modifier dans `backend/main.py` si nécessaire.

## 🐛 Résolution de Problèmes

### Erreur "Cannot find module '@/components'"

Vérifier `tsconfig.app.json` :
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### Erreur "LucideIcon not found"

Vérifier la version de `lucide-react` :
```bash
npm install lucide-react@latest
```

### Port déjà utilisé

**Backend** : Modifier le port dans `backend/main.py`
**Frontend** : Modifier dans `vite.config.ts` ou utiliser `npm run dev -- --port 3001`

## 📚 Documentation

- [Guide de Migration Lovable → Cursor](CURSOR_MIGRATION.md)
- [Guide d'Intégration Backend](INTEGRATION_GUIDE.md)
- [Documentation API](README_API.md)

## 🚀 Déploiement

### Backend (Render/Railway)

1. Créer un nouveau service Web
2. Build command : `pip install -r requirements.txt`
3. Start command : `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Frontend (Vercel/Netlify)

1. Connecter le repo GitHub
2. Build command : `npm run build`
3. Output directory : `dist`

## 📄 Licence

© 2024 APEX AI. Tous droits réservés.

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

---

**APEX AI** 🏎️ - *Ton Coach Virages IA*
