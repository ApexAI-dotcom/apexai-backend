# 🚀 ApexAI - Guide de démarrage complet

## 📁 Structure du projet

```
ApexAI/
├── backend/
│   ├── main.py              # FastAPI backend
│   ├── requirements.txt      # Dépendances Python
│   └── README.md             # Documentation backend
│
└── lovable-app/
    ├── src/
    │   └── pages/
    │       └── UploadPage.tsx  # Page d'upload React
    └── README_BACKEND.md       # Instructions frontend
```

## 🔧 BACKEND - Commandes exactes

### 1. Aller dans le dossier backend
```bash
cd backend
```

### 2. Créer environnement virtuel (optionnel)
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

### 4. Lancer le serveur FastAPI
```bash
# Option 1 : Directement avec Python
python main.py

# Option 2 : Avec uvicorn (recommandé)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

✅ **Backend disponible sur : http://localhost:8000**

## 🎨 FRONTEND - Commandes exactes

### 1. Ouvrir un NOUVEAU terminal et aller dans lovable-app
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

✅ **Frontend disponible sur : http://localhost:3000**

## 🎯 Test complet

1. ✅ Backend démarré sur `http://localhost:8000`
2. ✅ Frontend démarré sur `http://localhost:3000`
3. ✅ Ouvrir `http://localhost:3000` dans le navigateur
4. ✅ Glisser-déposer une vidéo dans la zone de drop
5. ✅ Cliquer sur "Analyser la vidéo"
6. ✅ Voir le résultat avec :
   - Score en grand (ex: 87%)
   - Badge de statut (ex: "Moyenne")
   - Cards avec analyses (CBV, Chroma, etc.)
   - Temps d'extraction

## 📡 API Backend

### POST `/api/upload`
**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` (fichier vidéo)

**Response:**
```json
{
  "success": true,
  "score": 87,
  "status": "moyenne",
  "analyses": {
    "CBV": "Haute",
    "Chroma": "Bonne",
    "Trajectoire": "Optimale",
    "Vitesse": "Élevée"
  },
  "extract": "3s"
}
```

## 🎨 Design Frontend

- ✅ Fond purple gradient (`from-purple-950 via-slate-900 to-purple-950`)
- ✅ Cards glassmorphism avec bordures purple
- ✅ Score en grand avec gradient purple-pink
- ✅ Badge de statut coloré selon le niveau
- ✅ Cards d'analyses avec fond purple/10
- ✅ Animations Framer Motion
- ✅ Responsive mobile/desktop

## 🐛 Dépannage

### Backend ne démarre pas
```bash
# Vérifier Python
python --version  # Doit être 3.8+

# Vérifier le port
netstat -ano | findstr :8000  # Windows
lsof -i :8000                  # Linux/Mac

# Réinstaller dépendances
pip install --upgrade -r requirements.txt
```

### Frontend ne démarre pas
```bash
# Vérifier Node.js
node --version  # Doit être 18+

# Nettoyer et réinstaller
rm -rf node_modules package-lock.json
npm install
```

### Erreur CORS
- Le backend accepte déjà `localhost:3000`
- Vérifier que le backend est bien démarré
- Vérifier l'URL dans `.env` : `VITE_API_URL=http://localhost:8000`

## ✅ Checklist finale

- [ ] Backend installé et démarré sur port 8000
- [ ] Frontend installé et démarré sur port 3000
- [ ] Test d'upload vidéo fonctionne
- [ ] Résultat affiché avec score et analyses
- [ ] Design purple correspond à l'image cible

---

**ApexAI Team** 🏎️
