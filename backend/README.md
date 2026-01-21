# ApexAI Backend

Backend FastAPI pour l'analyse de vidéos karting.

## 🚀 Installation

### 1. Créer un environnement virtuel (recommandé)
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

## 🏃 Lancer le serveur

```bash
# Méthode 1 : Directement avec Python
python main.py

# Méthode 2 : Avec uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Le serveur sera disponible sur : **http://localhost:8000**

## 📡 Endpoints

### POST `/api/upload`
Upload et analyse d'une vidéo.

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

### GET `/health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

## 🔧 Configuration

Le backend écoute sur le port **8000** par défaut.

Pour changer le port, modifiez `main.py` :
```python
uvicorn.run(
    "main:app",
    host="0.0.0.0",
    port=8000,  # Changez ici
    reload=True
)
```

## 📝 Notes

- Le backend simule actuellement l'analyse (scores aléatoires)
- Dans un vrai système, remplacez `analyze_video()` par votre logique d'analyse réelle
- CORS est configuré pour accepter les requêtes depuis `localhost:3000` et Lovable
