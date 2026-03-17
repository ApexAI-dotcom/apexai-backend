# 🚀 Guide de Démarrage - Backend Apex AI

Guide complet pour démarrer le backend Apex AI avec toutes les fonctionnalités (corner detection, coaching, scoring, visualisation).

---

## 📍 Localisation du Backend Complet

Le backend complet se trouve dans le dossier **`/src/api/`** :

```
src/api/
├── __init__.py          # Package Python
├── main.py              # Application FastAPI principale
├── routes.py            # Endpoints API (/api/v1/analyze, /api/v1/status)
├── services.py          # Logique métier (pipeline d'analyse complet)
├── models.py            # Modèles Pydantic (schemas de validation)
├── config.py            # Configuration (CORS, paths, limites)
└── utils.py             # Utilitaires (validation CSV)
```

**Pipeline d'analyse intégré :**
- `src/core/data_loader.py` - Chargement robuste des CSV
- `src/core/signal_processing.py` - Filtrage Savitzky-Golay GPS
- `src/analysis/geometry.py` - Calcul géométrie trajectoire + détection virages
- `src/analysis/scoring.py` - Système de scoring /100
- `src/analysis/coaching.py` - Génération conseils coaching IA
- `src/analysis/performance_metrics.py` - Métriques détaillées par virage
- `src/visualization/visualization.py` - Génération 10 graphiques F1-style

---

## ⚙️ Prérequis

- **Python** : 3.11+ (recommandé 3.11 ou 3.12)
- **pip** : Version récente
- **OS** : Windows, Linux, macOS

---

## 📦 Installation

### 1. Créer un environnement virtuel (recommandé)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 2. Installer les dépendances

Le backend nécessite **deux fichiers de requirements** :

```bash
# Depuis la racine du projet ApexAI/
pip install -r requirements/requirements.txt -r requirements_api.txt
```

**Dépendances principales :**
- `fastapi==0.109.0` - Framework web
- `uvicorn[standard]==0.27.0` - Serveur ASGI
- `pydantic==2.5.3` - Validation de données
- `pandas>=2.0.0` - Traitement CSV
- `numpy>=1.24.0` - Calculs numériques
- `scipy>=1.11.0` - Filtrage Savitzky-Golay
- `matplotlib>=3.7.0` - Génération graphiques
- `python-multipart==0.0.6` - Upload fichiers

**Note :** Si vous avez déjà installé les dépendances du pipeline (`requirements/requirements.txt`), vous pouvez installer uniquement les dépendances API :

```bash
pip install -r requirements_api.txt
```

---

## 🔧 Configuration (Optionnel)

### Variables d'environnement

Le backend fonctionne avec des valeurs par défaut, mais vous pouvez les personnaliser :

**Créer un fichier `.env` à la racine du projet** (optionnel) :

```bash
# Environnement (development | production)
ENVIRONMENT=development

# URL de base pour les images générées
BASE_URL=http://localhost:8000

# CORS - Origines autorisées (séparées par virgules)
CORS_ORIGINS=http://localhost:8080,http://localhost:3000,http://localhost:5173
```

**Valeurs par défaut (si .env non fourni) :**
- `ENVIRONMENT=development`
- `BASE_URL=http://localhost:8000`
- `CORS_ORIGINS=http://localhost:8080,http://localhost:3000,http://localhost:5173,http://127.0.0.1:8080,http://127.0.0.1:3000,http://127.0.0.1:5173`

---

## 🚀 Démarrage du Backend

### Méthode 1 : Script Python (Recommandé)

```bash
# Depuis la racine du projet
python run_api.py
```

**Avantages :**
- Configuration automatique
- Reload automatique en développement
- Port et host configurés

### Méthode 2 : Uvicorn directement

```bash
# Mode développement (avec reload automatique)
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Mode production (sans reload)
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

### Méthode 3 : Python direct

```bash
# Depuis la racine du projet
python -m src.api.main
```

**Note :** Cette méthode nécessite que `src.api.main` soit exécutable directement (ce qui est le cas grâce au `if __name__ == "__main__"`).

---

## ✅ Vérification que le Backend Fonctionne

### 1. Vérifier que le serveur démarre

Vous devriez voir dans la console :

```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 2. Tester l'endpoint Health Check

**Dans un navigateur :**
```
http://localhost:8000/health
```

**Avec curl :**
```bash
curl http://localhost:8000/health
```

**Réponse attendue :**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development"
}
```

### 3. Tester l'endpoint Root

**Dans un navigateur :**
```
http://localhost:8000/
```

**Réponse attendue :**
```json
{
  "name": "Apex AI API",
  "version": "1.0.0",
  "status": "operational",
  "description": "API d'analyse de télémétrie karting avec IA",
  "docs": "/docs",
  "endpoints": {
    "analyze": "/api/v1/analyze",
    "health": "/health"
  }
}
```

### 4. Accéder à la documentation interactive

**Swagger UI (recommandé) :**
```
http://localhost:8000/docs
```

**ReDoc :**
```
http://localhost:8000/redoc
```

**Note :** La documentation n'est disponible qu'en mode `development` (valeur par défaut).

---

## 📡 Endpoints Disponibles

### 1. `GET /` - Informations API

**Description :** Point d'entrée de l'API avec informations générales.

**Exemple :**
```bash
curl http://localhost:8000/
```

---

### 2. `GET /health` - Health Check

**Description :** Vérifier que le backend est opérationnel.

**Exemple :**
```bash
curl http://localhost:8000/health
```

**Réponse :**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development"
}
```

---

### 3. `POST /api/v1/analyze` - Analyser un CSV

**Description :** Analyser un fichier CSV de télémétrie karting.

**Request :**
```bash
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -F "file=@path/to/telemetry.csv"
```

**Response :**
```json
{
  "success": true,
  "analysis_id": "abc12345",
  "timestamp": "2024-01-15T10:30:00",
  "corners_detected": 22,
  "lap_time": 125.3,
  "performance_score": {
    "overall_score": 85.0,
    "grade": "A",
    "breakdown": {
      "apex_precision": 27.0,
      "trajectory_consistency": 16.0,
      "apex_speed": 22.0,
      "sector_times": 20.0
    },
    "percentile": 78
  },
  "corner_analysis": [
    {
      "corner_id": 1,
      "corner_number": 1,
      "corner_type": "right",
      "apex_speed_real": 65.3,
      "apex_speed_optimal": 72.1,
      "speed_efficiency": 0.906,
      "apex_distance_error": 2.3,
      "apex_direction_error": "right",
      "lateral_g_max": 2.1,
      "time_lost": 0.4,
      "grade": "B",
      "score": 78.0
    }
  ],
  "coaching_advice": [
    {
      "priority": 1,
      "category": "braking",
      "impact_seconds": 0.4,
      "corner": 3,
      "message": "Virage 3 : Tu freines 8m trop tôt (-0.4s perdu)",
      "explanation": "Détection du point de freinage optimal...",
      "difficulty": "facile"
    }
  ],
  "plots": {
    "trajectory_2d": "http://localhost:8000/output/abc12345/trajectory_2d.png",
    "speed_heatmap": "http://localhost:8000/output/abc12345/speed_heatmap.png",
    "lateral_g_chart": "http://localhost:8000/output/abc12345/lateral_g_chart.png",
    "speed_trace": "http://localhost:8000/output/abc12345/speed_trace.png",
    "throttle_brake": "http://localhost:8000/output/abc12345/throttle_brake.png",
    "sector_times": "http://localhost:8000/output/abc12345/sector_times.png",
    "apex_precision": "http://localhost:8000/output/abc12345/apex_precision.png",
    "performance_radar": "http://localhost:8000/output/abc12345/performance_radar.png",
    "performance_score_breakdown": "http://localhost:8000/output/abc12345/performance_score_breakdown.png",
    "corner_heatmap": "http://localhost:8000/output/abc12345/corner_heatmap.png"
  },
  "statistics": {
    "processing_time_seconds": 2.3,
    "data_points": 1250,
    "best_corners": [5, 12, 18],
    "worst_corners": [3, 7, 15],
    "avg_apex_distance": 1.2,
    "avg_apex_speed_efficiency": 0.87
  }
}
```

**Limites :**
- Taille max : **20 MB**
- Format : **CSV uniquement**
- Colonnes requises : **Latitude**, **Longitude**, **Speed** (ou variantes)

**Formats supportés :**
- MyChron (AIM)
- RaceBox
- CSV générique avec colonnes GPS

---

### 4. `GET /api/v1/status/{analysis_id}` - Statut d'une analyse

**Description :** Vérifier le statut d'une analyse (pour futures implémentations async).

**Exemple :**
```bash
curl http://localhost:8000/api/v1/status/abc12345
```

**Réponse :**
```json
{
  "analysis_id": "abc12345",
  "status": "completed",
  "message": "Analyse synchrone (toujours completed)"
}
```

**Note :** Actuellement, toutes les analyses sont synchrones. Cet endpoint est préparé pour de futures implémentations async.

---

## 📂 Structure des Dossiers Créés

Le backend crée automatiquement les dossiers suivants :

```
ApexAI/
├── temp/              # Fichiers CSV temporaires (supprimés après analyse)
└── output/            # Graphiques générés (servis via /output/{analysis_id}/)
    └── {analysis_id}/
        ├── trajectory_2d.png
        ├── speed_heatmap.png
        ├── lateral_g_chart.png
        ├── speed_trace.png
        ├── throttle_brake.png
        ├── sector_times.png
        ├── apex_precision.png
        ├── performance_radar.png
        ├── performance_score_breakdown.png
        └── corner_heatmap.png
```

---

## 🔍 Dépannage

### Problème : Port 8000 déjà utilisé

**Solution 1 :** Changer le port dans `run_api.py` ou via uvicorn :

```bash
uvicorn src.api.main:app --port 8001
```

**Solution 2 :** Trouver et arrêter le processus utilisant le port :

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS
lsof -ti:8000 | xargs kill -9
```

---

### Problème : Module non trouvé (`ModuleNotFoundError`)

**Cause :** Le Python path n'inclut pas le répertoire racine.

**Solution :** S'assurer d'exécuter depuis la racine du projet :

```bash
# Depuis ApexAI/ (racine)
python run_api.py
```

Ou utiliser `PYTHONPATH` :

```bash
# Windows
set PYTHONPATH=%CD%
python run_api.py

# Linux/macOS
export PYTHONPATH=$PWD
python run_api.py
```

---

### Problème : Erreur CORS depuis le frontend

**Cause :** L'origine du frontend n'est pas dans `CORS_ORIGINS`.

**Solution :** Ajouter l'origine dans `.env` ou modifier `src/api/config.py` :

```python
CORS_ORIGINS_STR = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8080,http://localhost:3000,http://YOUR_FRONTEND_URL"
)
```

---

### Problème : Erreur lors de l'analyse CSV

**Vérifications :**
1. Le fichier CSV contient bien les colonnes GPS (Latitude, Longitude)
2. Le fichier fait moins de 20 MB
3. Le fichier est bien un CSV (pas Excel, pas JSON)
4. Les colonnes numériques sont bien formatées (virgule ou point décimal)

**Logs :** Vérifier les logs dans la console pour plus de détails.

---

## 🧪 Test Complet avec un Fichier CSV

### 1. Préparer un fichier CSV de test

Créez un fichier `test_telemetry.csv` avec au minimum :

```csv
Time,Latitude,Longitude,Speed
0.0,46.2041,6.1434,50.0
0.1,46.2042,6.1435,52.0
0.2,46.2043,6.1436,55.0
...
```

### 2. Uploader via curl

```bash
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -F "file=@test_telemetry.csv" \
  -o result.json
```

### 3. Vérifier le résultat

```bash
# Afficher le JSON
cat result.json | python -m json.tool

# Ou ouvrir dans un éditeur
code result.json
```

### 4. Accéder aux graphiques

Les URLs des graphiques sont dans `result.json` sous `plots`. Ouvrez-les dans un navigateur :

```
http://localhost:8000/output/{analysis_id}/trajectory_2d.png
```

---

## 📊 Monitoring et Logs

Le backend log toutes les requêtes dans la console :

```
INFO:     ➡️  POST /api/v1/analyze - 127.0.0.1
INFO:     🏁 New analysis request: abc12345 - telemetry.csv
INFO:     [abc12345] Loading data...
INFO:     [abc12345] Filtering...
INFO:     [abc12345] Geometry...
INFO:     [abc12345] Detecting corners...
INFO:     [abc12345] 22 corners detected
INFO:     [abc12345] Calculating score...
INFO:     [abc12345] Generating plots...
INFO:     [abc12345] ✅ Analysis completed successfully
INFO:     ⬅️  POST /api/v1/analyze - 200 - 2.34s
```

**Headers de réponse :**
- `X-Process-Time` : Temps de traitement en secondes

---

## 🚀 Déploiement Production

### Variables d'environnement recommandées

```bash
ENVIRONMENT=production
BASE_URL=https://your-domain.com
CORS_ORIGINS=https://your-frontend.com
```

### Commande de démarrage production

```bash
uvicorn src.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info
```

**Recommandations :**
- Utiliser un reverse proxy (Nginx, Traefik)
- Activer HTTPS
- Configurer les limites de taille de fichier
- Monitorer les performances
- Sauvegarder les logs

---

## 📚 Documentation Complémentaire

- **README_API.md** : Documentation détaillée de l'API
- **src/api/main.py** : Code source de l'application FastAPI
- **src/api/routes.py** : Définition des endpoints
- **src/api/services.py** : Logique métier complète

---

## ✅ Checklist de Démarrage

- [ ] Python 3.11+ installé
- [ ] Environnement virtuel créé et activé
- [ ] Dépendances installées (`pip install -r requirements/requirements.txt -r requirements_api.txt`)
- [ ] Fichier `.env` créé (optionnel)
- [ ] Backend démarré (`python run_api.py`)
- [ ] Health check réussi (`curl http://localhost:8000/health`)
- [ ] Documentation accessible (`http://localhost:8000/docs`)
- [ ] Test d'upload CSV réussi

---

**🎉 Le backend est maintenant prêt à analyser vos fichiers CSV de télémétrie karting !**

Pour toute question ou problème, consultez les logs dans la console ou la documentation dans `README_API.md`.
