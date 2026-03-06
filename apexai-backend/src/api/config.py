#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API Configuration
Configuration de l'API REST
"""

import os
from pathlib import Path


class Settings:
    """Configuration de l'API"""
    
    APP_NAME = "Apex AI API"
    VERSION = "1.0.0"
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    
    # Limites upload (50MB par défaut, configurable via MAX_UPLOAD_SIZE en bytes)
    _max_upload_bytes = int(os.getenv("MAX_UPLOAD_SIZE", 52428800))
    MAX_FILE_SIZE_BYTES = _max_upload_bytes
    MAX_FILE_SIZE_MB = _max_upload_bytes // (1024 * 1024)
    
    # Paths (relatifs depuis project_root)
    PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
    TEMP_DIR = str(PROJECT_ROOT / "temp")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(PROJECT_ROOT / "output"))
    
    # Créer dossiers si nécessaire
    Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    # URL de base pour les images (OBLIGATOIRE en prod: Railway, Render)
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
    
    # CORS (string séparée par virgules)
    CORS_ORIGINS_STR = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8080,http://localhost:3000,http://localhost:5173,http://127.0.0.1:8080,http://127.0.0.1:3000,http://127.0.0.1:5173,https://*.lovable.app,https://*.lovable.dev"
    )
    CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]
    
    # Supabase (service_role pour webhook Stripe / RLS bypass)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")

    # Stripe Configuration
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    # Grok API Configuration
    GROK_API_KEY = os.getenv("GROK_API_KEY", "")
    GROK_API_URL = os.getenv("GROK_API_URL", "https://api.x.ai/v1")
    
    # Redis (Railway REDIS_URL)
    REDIS_URL = os.getenv("REDIS_URL", "")

    # Docs en prod (Render, etc.)
    DOCS_ENABLED = os.getenv("DOCS_ENABLED", "false").lower() == "true"

    # Mock Video AI (Gratuit - Pas de paiement)
    MOCK_VIDEO_AI = os.getenv("MOCK_VIDEO_AI", "true").lower() == "true"  # ← Gratuit !
    
    # Mock réponse (au lieu API payante)
    MOCK_SUMMARY = """
🎬 VIDÉO ANALYSÉE PAR APEXAI PRO !

📊 Durée: 2min47s
👥 3 personnes détectées
💬 127 mots transcrits
🔥 Moments forts: 00:23, 01:45

📝 RÉSUMÉ IA:
Votre présentation business est excellente ! 
Points forts: accroche immédiate, chiffres concrets.
Amélioration: slide 3 → animation + pause.

#Tags: business pitch startup investissement
"""


settings = Settings()
