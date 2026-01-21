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
    
    # Limites
    MAX_FILE_SIZE_MB = 20
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    
    # Paths (relatifs depuis project_root)
    PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
    TEMP_DIR = str(PROJECT_ROOT / "temp")
    OUTPUT_DIR = str(PROJECT_ROOT / "output")
    
    # Créer dossiers si nécessaire
    Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    # URL de base pour les images (à adapter selon déploiement)
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
    
    # CORS (string séparée par virgules)
    CORS_ORIGINS_STR = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,https://*.lovable.app,https://*.lovable.dev"
    )
    CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]


settings = Settings()
