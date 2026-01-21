# 🚀 Apex AI - API REST Documentation

API REST production-ready pour analyse de télémétrie karting avec IA.

## 📋 Quick Start

### Installation

```bash
# Installer toutes les dépendances
pip install -r requirements.txt -r requirements_api.txt
```

### Lancement Local

```bash
# Mode développement (avec reload)
uvicorn src.api.main:app --reload

# Mode production
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

**API disponible sur :** http://localhost:8000
**Documentation interactive :** http://localhost:8000/docs
**ReDoc :** http://localhost:8000/redoc

## 📡 Endpoints

### POST `/api/v1/analyze`

Analyser un fichier CSV de télémétrie.

**Request :**
```bash
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -F "file=@telemetry.csv"
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
      "explanation": "...",
      "difficulty": "facile"
    }
  ],
  "plots": {
    "trajectory_2d": "http://localhost:8000/output/abc12345/trajectory.png",
    "speed_heatmap": "http://localhost:8000/output/abc12345/speed_heatmap.png",
    ...
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

### GET `/health`

Health check endpoint.

**Response :**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development"
}
```

### GET `/`

Informations sur l'API.

## 🔗 Intégration React (Lovable.dev)

### Exemple TypeScript

```typescript
// Dans ta page /upload
const handleUpload = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const response = await fetch('http://localhost:8000/api/v1/analyze', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || 'Erreur lors de l\'analyse');
    }
    
    const data = await response.json();
    
    if (data.success) {
      // Afficher score
      console.log("Score:", data.performance_score.overall_score);
      console.log("Grade:", data.performance_score.grade);
      
      // Afficher graphiques
      console.log("Graphiques:", data.plots);
      // data.plots.trajectory_2d → URL de l'image
      
      // Afficher conseils
      data.coaching_advice.forEach(advice => {
        console.log(`${advice.priority}. ${advice.message}`);
      });
      
      // Mettre à jour l'UI
      setScore(data.performance_score.overall_score);
      setPlots(data.plots);
      setAdvice(data.coaching_advice);
    }
  } catch (error) {
    console.error('Erreur:', error);
  }
};
```

### Exemple avec React Hook

```typescript
// useApexAnalysis.ts
import { useState } from 'react';

interface AnalysisResponse {
  success: boolean;
  analysis_id: string;
  performance_score: {
    overall_score: number;
    grade: string;
  };
  plots: {
    trajectory_2d?: string;
    // ...
  };
  coaching_advice: Array<{
    message: string;
    impact_seconds: number;
  }>;
}

export const useApexAnalysis = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  
  const analyze = async (file: File) => {
    setLoading(true);
    setError(null);
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await fetch(
        process.env.NEXT_PUBLIC_API_URL + '/api/v1/analyze',
        {
          method: 'POST',
          body: formData
        }
      );
      
      const data = await response.json();
      
      if (data.success) {
        setResult(data);
      } else {
        setError(data.message || 'Erreur inconnue');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur réseau');
    } finally {
      setLoading(false);
    }
  };
  
  return { analyze, loading, error, result };
};
```

## 🌐 Déploiement

### Render.com

1. **Créer un nouveau Web Service**
2. **Connecter le repo GitHub**
3. **Configuration :**
   - **Build Command :** `pip install -r requirements.txt -r requirements_api.txt`
   - **Start Command :** `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
   - **Environment :** `ENVIRONMENT=production`
   - **BASE_URL :** `https://votre-api.render.com`

4. **Variables d'environnement :**
   ```
   ENVIRONMENT=production
   BASE_URL=https://votre-api.render.com
   CORS_ORIGINS=https://*.lovable.app,https://*.lovable.dev
   ```

5. **Déployer !**

### Docker

```bash
# Build
docker build -t apex-ai-api .

# Run
docker run -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e BASE_URL=http://localhost:8000 \
  apex-ai-api
```

## 🔧 Configuration

Variables d'environnement :

- `ENVIRONMENT` : `development` | `production` (défaut: `development`)
- `BASE_URL` : URL de base pour les images (défaut: `http://localhost:8000`)
- `CORS_ORIGINS` : Origines CORS autorisées (séparées par virgules)
- `MAX_FILE_SIZE_MB` : Taille max fichier (défaut: 20 MB)

## 📊 Format de Réponse

### Performance Score

```typescript
interface PerformanceScore {
  overall_score: number;      // /100
  grade: "A+" | "A" | "B" | "C" | "D";
  breakdown: {
    apex_precision: number;    // /30
    trajectory_consistency: number;  // /20
    apex_speed: number;        // /25
    sector_times: number;      // /25
  };
  percentile: number;          // 0-100
}
```

### Coaching Advice

```typescript
interface CoachingAdvice {
  priority: number;            // 1-5 (1 = plus impact)
  category: "braking" | "apex" | "speed" | "trajectory" | "global";
  impact_seconds: number;      // Temps perdu/gagné
  corner?: number;             // Numéro virage (si applicable)
  message: string;             // Message court
  explanation: string;         // Explication détaillée
  difficulty: "facile" | "moyen" | "difficile";
}
```

## ⚠️ Limitations

- **Taille max fichier :** 20 MB
- **Format :** CSV uniquement
- **Timeout :** 5 minutes par analyse
- **Rate limiting :** À implémenter en production

## 🐛 Dépannage

### CORS Error
→ Vérifier que `BASE_URL` et `CORS_ORIGINS` sont bien configurés

### File Upload Failed
→ Vérifier taille du fichier (< 20MB)
→ Vérifier format (CSV)

### Images non chargées
→ Vérifier que `BASE_URL` pointe vers l'API
→ Vérifier que le dossier `output/` est accessible

## 📚 Documentation Complète

Consultez http://localhost:8000/docs pour la documentation interactive Swagger.

---

**Apex AI Team** 🏎️
