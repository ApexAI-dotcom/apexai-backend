# 🚀 Guide d'intégration ApexAI - Lovable

## 📁 Structure finale

```
ApexAI/
├── backend/
│   ├── main.py              # FastAPI avec analyse Lovable
│   └── requirements.txt     # Dépendances (inclut opencv-python)
│
└── lovable-app/
    ├── src/
    │   ├── pages/
    │   │   ├── index.tsx        # Page d'accueil (Hero + Features)
    │   │   └── UploadPage.tsx   # Page d'upload avec résultats purple
    │   ├── components/
    │   │   └── layout/
    │   │       └── Layout.tsx   # Layout wrapper
    │   └── App.tsx              # Router avec / et /upload
```

## 🔧 BACKEND - Intégration Lovable

### 1. Remplacer la fonction `analyze_video_lovable()`

Dans `backend/main.py`, ligne ~30, remplacez la fonction `analyze_video_lovable()` par votre code Python Lovable complet :

```python
def analyze_video_lovable(file_path: str) -> Dict[str, Any]:
    """
    Analyse une vidéo avec la logique Lovable.
    
    REMPLACEZ CETTE FONCTION PAR VOTRE CODE LOVABLE COMPLET
    """
    # VOTRE CODE LOVABLE ICI
    # Exemple de structure attendue :
    
    # 1. Charger la vidéo
    cap = cv2.VideoCapture(file_path)
    
    # 2. Votre analyse Lovable
    # ... votre code ...
    
    # 3. Retourner le résultat
    return {
        "score": 87,  # Score calculé
        "status": "moyenne",  # excellente/bonne/moyenne/à améliorer
        "analyses": {
            "CBV": "Haute",
            "Chroma": "Bonne",
            "Trajectoire": "Optimale",
            "Vitesse": "Élevée"
        },
        "extract": "3s"
    }
```

### 2. Installer les dépendances

```bash
cd backend
pip install -r requirements.txt
```

### 3. Lancer le backend

```bash
python main.py
# OU
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 🎨 FRONTEND - Pages créées

### Page d'accueil (`/`)
- Hero section avec badge "Propulsé par l'IA"
- Stats (12,847 tours, +7.2s gain, 94% précision)
- Features (Analyse IA, Score /100, Compatible MyChron)
- Testimonials (Lucas M., Marie D.)
- CTA section
- Footer

### Page Upload (`/upload`)
- Drag & drop vidéo
- Preview vidéo
- Upload vers `/api/upload`
- Affichage résultats purple :
  - Score en grand (ex: 87%)
  - Badge statut coloré (ex: "Moyenne")
  - Cards analyses (CBV, Chroma, Trajectoire, Vitesse)
  - Temps d'extraction

## 🚀 Commandes de démarrage

### Terminal 1 - Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Terminal 2 - Frontend
```bash
cd lovable-app
npm install
npm run dev
```

## ✅ Vérification

1. ✅ Backend sur `http://localhost:8000`
2. ✅ Frontend sur `http://localhost:3000`
3. ✅ Page d'accueil (`/`) avec hero section
4. ✅ Page upload (`/upload`) avec drag & drop
5. ✅ Résultats affichés en purple (score, badge, cards)

## 📝 Notes importantes

- Le backend utilise OpenCV pour ouvrir les vidéos
- Remplacez `analyze_video_lovable()` par votre code Lovable réel
- Le format de retour JSON est fixe (score, status, analyses, extract)
- Le frontend est déjà configuré pour afficher ces données

## 🔄 Prochaines étapes

1. Intégrer votre code Lovable dans `analyze_video_lovable()`
2. Tester avec une vraie vidéo
3. Ajuster les analyses selon vos besoins
4. Personnaliser le design si nécessaire

---

**ApexAI Team** 🏎️
