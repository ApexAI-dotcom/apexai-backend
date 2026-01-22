# 🚀 Guide de Démarrage Rapide - APEX AI

## ⚡ Démarrage en 2 Commandes

### Terminal 1 : Backend

```bash
cd backend
python main.py
```

**✅ Backend démarré sur http://localhost:8000**

### Terminal 2 : Frontend

```bash
cd lovable-app
npm run dev
```

**✅ Frontend démarré sur http://localhost:3000**

---

## 📋 Checklist de Vérification

### ✅ Backend

- [ ] Python 3.11+ installé
- [ ] Dépendances installées (`pip install -r requirements.txt`)
- [ ] Serveur démarré sur port 8000
- [ ] API accessible sur http://localhost:8000/docs

### ✅ Frontend

- [ ] Node.js 18+ installé
- [ ] Dépendances installées (`npm install`)
- [ ] Serveur démarré sur port 3000
- [ ] Application accessible sur http://localhost:3000

### ✅ Tests Fonctionnels

- [ ] Page d'accueil (`/`) s'affiche
- [ ] Page upload (`/upload`) fonctionne
- [ ] Upload CSV MyChron fonctionne
- [ ] Résultats s'affichent avec score purple
- [ ] Dashboard (`/dashboard`) accessible
- [ ] Pricing (`/pricing`) accessible
- [ ] Profile (`/profile`) accessible
- [ ] Page 404 (`/inexistant`) fonctionne

---

## 🔧 Commandes Utiles

### Backend

```bash
# Installation
cd backend
pip install -r requirements.txt

# Démarrage
python main.py

# OU avec uvicorn directement
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Test API
curl http://localhost:8000/
```

### Frontend

```bash
# Installation
cd lovable-app
npm install

# Démarrage développement
npm run dev

# Build production
npm run build

# Preview build
npm run preview

# Linter
npm run lint
```

---

## 🐛 Résolution de Problèmes

### Port 8000 déjà utilisé (Backend)

```bash
# Modifier le port dans backend/main.py
# OU utiliser uvicorn avec un autre port
uvicorn main:app --port 8001
```

### Port 3000 déjà utilisé (Frontend)

```bash
# Modifier vite.config.ts
# OU utiliser un autre port
npm run dev -- --port 3001
```

### Erreur "Module not found"

```bash
# Backend
pip install -r requirements.txt

# Frontend
npm install
```

### Erreur CORS

Vérifier que le backend autorise `http://localhost:3000` dans `backend/main.py` :

```python
allow_origins=[
    "http://localhost:3000",
    "http://localhost:5173",
    # ...
]
```

---

## 📊 Test Complet

1. **Démarrer Backend** : `cd backend && python main.py`
2. **Démarrer Frontend** : `cd lovable-app && npm run dev`
3. **Ouvrir** : http://localhost:3000
4. **Tester Upload** :
   - Aller sur http://localhost:3000/upload
   - Glisser un fichier CSV MyChron
   - Vérifier le preview
   - Cliquer "Analyser"
   - Vérifier les résultats purple

---

## ✅ Migration 100% Complète !

Toutes les routes sont configurées :
- ✅ `/` - Page d'accueil
- ✅ `/upload` - Upload CSV
- ✅ `/dashboard` - Dashboard
- ✅ `/pricing` - Tarifs
- ✅ `/profile` - Profil
- ✅ `/*` - 404

Tous les composants sont harmonisés :
- ✅ Design purple glassmorphism
- ✅ Layout cohérent
- ✅ Shadcn UI utilisé
- ✅ Framer Motion animations

**APEX AI est prêt pour la production !** 🏎️
