#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API REST
Application FastAPI principale
Version: 1.0.0
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
import time
import os
from pathlib import Path

# Initialiser le logging avant les imports qui l'utilisent
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from .routes import router
from .config import settings

# Import du router Stripe
try:
    from .stripe_routes import router as stripe_router
    logger.info("✓ Stripe router loaded successfully")
except ImportError as e:
    logger.warning(f"⚠ Warning: Could not import stripe router: {e}")
    logger.warning("  Stripe endpoints will not be available")
    stripe_router = None

# Créer application FastAPI
app = FastAPI(
    title="Apex AI API",
    description="API d'analyse de télémétrie karting avec IA - Scoring /100 et Coaching",
    version="1.0.0",
    docs_url="/docs" if (settings.ENVIRONMENT == "development" or settings.DOCS_ENABLED) else None,
    redoc_url="/redoc" if (settings.ENVIRONMENT == "development" or settings.DOCS_ENABLED) else None
)

# CORS pour Frontend et Lovable.dev
allowed_origins = list(settings.CORS_ORIGINS)
if not allowed_origins:
    allowed_origins = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://localhost:8080"]
if settings.ENVIRONMENT == "development":
    # Ajouter origines locales si pas déjà présentes
    dev_origins = [
        "http://localhost:8080",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    for origin in dev_origins:
        if origin not in allowed_origins:
            allowed_origins.append(origin)
else:
    # En production, accepter toutes les origines Lovable
    prod_origins = [
        "https://*.lovable.app",
        "https://*.lovable.dev"
    ]
    for origin in prod_origins:
        if origin not in allowed_origins:
            allowed_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-Process-Time"]
)

# Compression GZip
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Servir les images statiques
output_dir = Path(settings.OUTPUT_DIR)
output_dir.mkdir(parents=True, exist_ok=True)
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")

# Middleware timing et logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware pour logger les requêtes et calculer le temps de traitement"""
    start_time = time.time()
    
    logger.info(f"➡️  {request.method} {request.url.path} - {request.client.host if request.client else 'unknown'}")
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        logger.info(
            f"⬅️  {request.method} {request.url.path} "
            f"- {response.status_code} - {duration:.2f}s"
        )
        
        response.headers["X-Process-Time"] = str(round(duration, 3))
        return response
    
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"❌ {request.method} {request.url.path} - ERROR - {duration:.2f}s: {str(e)}",
            exc_info=True
        )
        raise


# Routes
app.include_router(router, prefix="/api/v1", tags=["analysis"])

# Routes Stripe
if stripe_router:
    app.include_router(stripe_router)

# Importer process-video depuis routes pour accès direct /api/process-video
from .routes import process_video
app.post("/api/process-video")(process_video)


@app.get("/", tags=["info"])
async def root():
    """
    Point d'entrée de l'API.
    
    Returns:
        Informations sur l'API
    """
    return {
        "name": "Apex AI API",
        "version": "1.0.0",
        "status": "operational",
        "description": "API d'analyse de télémétrie karting avec IA",
        "docs": "/docs" if (settings.ENVIRONMENT == "development" or settings.DOCS_ENABLED) else "disabled",
        "endpoints": {
            "analyze": "/api/v1/analyze",
            "health": "/health"
        }
    }


@app.get("/health", tags=["info"])
async def health():
    """
    Health check endpoint.
    
    Returns:
        Statut de santé de l'API
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


# Handler d'erreurs global
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handler global pour les erreurs non capturées"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "message": "Une erreur inattendue s'est produite"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development"
    )
