#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API REST
Application FastAPI principale
Version: 1.0.0
"""

from contextlib import asynccontextmanager
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

# Redis client global (connexion propre on_shutdown)
redis_client = None

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown : connexion Redis"""
    global redis_client
    if settings.REDIS_URL:
        try:
            from redis.asyncio import Redis
            redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            await redis_client.ping()
            logger.info("✓ Redis connected")
        except Exception as e:
            logger.warning(f"⚠ Redis not available: {e}")
            redis_client = None
    else:
        redis_client = None
    app.state.redis = redis_client
    yield
    if redis_client:
        await redis_client.aclose()
        logger.info("✓ Redis connection closed")


# Créer application FastAPI
app = FastAPI(
    title="Apex AI API",
    description="API d'analyse de télémétrie karting avec IA - Scoring /100 et Coaching",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if (settings.ENVIRONMENT == "development" or settings.DOCS_ENABLED) else None,
    redoc_url="/redoc" if (settings.ENVIRONMENT == "development" or settings.DOCS_ENABLED) else None
)

# CORS - lire depuis CORS_ORIGINS (env var). "*" = toutes origines (preview Vercel)
cors_origins_str = os.environ.get("CORS_ORIGINS", "http://localhost:8080")
if cors_origins_str.strip() == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True if "*" not in allow_origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"]
)

# Compression GZip
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Servir les images statiques (graphiques matplotlib)
output_dir = Path(settings.OUTPUT_DIR)
output_dir.mkdir(parents=True, exist_ok=True)
app.mount("/output", StaticFiles(directory=str(output_dir)), name="output")
if settings.ENVIRONMENT == "production" and "localhost" in settings.BASE_URL:
    logger.warning("BASE_URL points to localhost - graphiques ne s'afficheront pas en prod. Set BASE_URL on Railway/Render.")

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
            "analyse": "/api/v1/analyse/{cache_key}",
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
