# 🚀 Instructions de démarrage - ApexAI

## Backend (FastAPI)

### 1. Aller dans le dossier backend
```bash
cd backend
```

### 2. Créer un environnement virtuel (optionnel mais recommandé)
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Lancer le serveur
```bash
# Option 1 : Directement
python main.py

# Option 2 : Avec uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Le backend sera sur : **http://localhost:8000**

## Frontend (React)

### 1. Aller dans le dossier lovable-app
```bash
cd lovable-app
```

### 2. Installer les dépendances (si pas déjà fait)
```bash
npm install
```

### 3. Lancer le serveur de développement
```bash
npm run dev
```

Le frontend sera sur : **http://localhost:3000**

## ✅ Vérification

1. Backend démarré sur `http://localhost:8000`
2. Frontend démarré sur `http://localhost:3000`
3. Ouvrir `http://localhost:3000` dans le navigateur
4. Glisser-déposer une vidéo
5. Voir le résultat avec score et analyses

## 🐛 Dépannage

### Backend ne démarre pas
- Vérifier que Python 3.8+ est installé
- Vérifier que le port 8000 n'est pas utilisé
- Vérifier que toutes les dépendances sont installées

### Frontend ne peut pas contacter le backend
- Vérifier que le backend est bien démarré
- Vérifier l'URL dans `.env` : `VITE_API_URL=http://localhost:8000`
- Vérifier les CORS dans `backend/main.py`

### Erreur CORS
- Le backend accepte déjà les requêtes depuis `localhost:3000`
- Si problème, vérifier la config CORS dans `backend/main.py`
