#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de lancement de l'API REST Apex AI
Usage: python run_api.py (depuis apexai-backend/)
"""

import sys
from pathlib import Path

# Ajouter le répertoire apexai-backend au path
backend_root = Path(__file__).parent
sys.path.insert(0, str(backend_root))

import uvicorn
from src.api.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level="info",
    )
