#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API Routes
Endpoints de l'API REST
"""

import hashlib
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional
import numpy as np

from fastapi import APIRouter, File, Form, Header, Request, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from .config import settings
from .models import AnalysisResponse, ErrorResponse
from .services import AnalysisService
from .utils import validate_csv_file, sanitize_json_data
from src.core.subscription_service import check_analysis_limit, increment_analysis_count

# Résolution user_id depuis JWT (optionnel pour limite abonnement)
_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
_supabase = None
if _SUPABASE_URL and _SUPABASE_SERVICE_KEY and _SUPABASE_SERVICE_KEY != "ton_service_role_key":
    try:
        from supabase import create_client
        _supabase = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_KEY)
    except ImportError:
        pass


def _get_user_id_from_authorization(authorization: Optional[str]) -> Optional[str]:
    """Extrait user_id (UUID) depuis le header Authorization Bearer <jwt>."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "").strip()
    if not _supabase:
        return None
    try:
        user_response = _supabase.auth.get_user(jwt=token)
        user = user_response.user if hasattr(user_response, "user") else user_response
        if not user:
            return None
        return user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    except Exception as e:
        logger.debug("get_user_id_from_authorization: %s", e)
        return None


router = APIRouter()
logger = logging.getLogger(__name__)

REDIS_CACHE_TTL = 3600
REDIS_KEY_PREFIX = "analysis:v2:"


@router.post(
    "/parse-laps",
    summary="Détecter les tours d'un fichier CSV",
    description="Reçoit un CSV en FormData, retourne la liste des tours avec lap_number, lap_time_seconds, points_count, is_outlier (tours stand/prépa si temps > 1.5× médiane).",
)
async def parse_laps(
    file: UploadFile = File(..., description="Fichier CSV de télémétrie"),
):
    """Parse le CSV et retourne les tours détectés (réutilise la logique detect_laps)."""
    try:
        validation_error = await validate_csv_file(file)
        if validation_error:
            raise HTTPException(
                status_code=400,
                detail={"success": False, "error": "Validation error", "message": validation_error},
            )
        service = AnalysisService()
        laps = await service.parse_laps(file)
        return JSONResponse(content={"success": True, "laps": laps})
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"parse-laps ValueError: {e}")
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": "Processing error", "message": str(e)},
        )
    except Exception as e:
        logger.error(f"parse-laps error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": "Internal server error", "message": str(e)},
        )


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Erreur de validation"},
        403: {"model": ErrorResponse, "description": "Limite d'analyses atteinte (abonnement)"},
        413: {"model": ErrorResponse, "description": "Fichier trop volumineux"},
        500: {"model": ErrorResponse, "description": "Erreur serveur"}
    },
    summary="Analyser un fichier de télémétrie",
    description="""
    Analyser un fichier CSV de télémétrie karting.
    
    **Formats supportés :**
    - MyChron (AIM)
    - RaceBox
    - CSV générique avec colonnes GPS
    
    **Retourne :**
    - Score de performance /100 avec breakdown
    - Analyse détaillée de chaque virage (top 10)
    - Top 5 conseils de coaching personnalisés
    - URLs des 10 graphiques générés
    - Statistiques de l'analyse
    
    **Limites :**
    - Taille max : 50 MB (configurable via MAX_UPLOAD_SIZE)
    - Format : CSV uniquement
    - Colonnes requises : Latitude, Longitude, Speed
    """
)
async def analyze_telemetry(
    request: Request,
    file: UploadFile = File(..., description="Fichier CSV de télémétrie"),
    lap_filter: Optional[str] = Form(None, description="JSON array des numéros de tours à inclure, ex: [1,2,3]"),
    track_condition: str = Form("dry", description="Condition piste: dry, damp, wet, rain"),
    track_temperature: Optional[str] = Form(None, description="Température piste en °C"),
    session_name: Optional[str] = Form(None, description="Nom optionnel de la session"),
    authorization: Optional[str] = Header(None, description="Bearer JWT pour limite abonnement"),
) -> AnalysisResponse:
    """
    Analyser un fichier de télémétrie.
    
    Args:
        file: Fichier CSV uploadé
        lap_filter: Optionnel, liste JSON des numéros de tours à analyser (ex: [1,2,3]). Si vide, tous les tours.
    
    Returns:
        AnalysisResponse avec résultats complets
    """
    analysis_id = str(uuid.uuid4())[:8]
    logger.info(f"🏁 New analysis request: {analysis_id} - {file.filename}")

    user_id = _get_user_id_from_authorization(authorization)
    if user_id and not check_analysis_limit(user_id):
        raise HTTPException(
            status_code=403,
            detail={
                "success": False,
                "error": "limit_reached",
                "message": (
                    "Vous avez atteint la limite d'analyses de votre abonnement ce mois-ci. "
                    "Passez au plan Racer ou Team pour des analyses illimitées."
                ),
            },
        )

    lap_list = []
    if lap_filter and lap_filter.strip():
        try:
            parsed = json.loads(lap_filter)
            if isinstance(parsed, list):
                lap_list = [int(x) for x in parsed if isinstance(x, (int, float))]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    cond = (track_condition or "dry").strip().lower()
    if cond not in ("dry", "damp", "wet", "rain"):
        cond = "dry"
    temp_c = None
    if track_temperature is not None and track_temperature.strip():
        try:
            temp_c = float(track_temperature.strip().replace(",", "."))
        except ValueError:
            pass

    cache_key = hashlib.md5((file.filename or "unknown").encode()).hexdigest()
    redis = getattr(request.app.state, "redis", None)

    try:
        # Validation
        validation_error = await validate_csv_file(file)
        if validation_error:
            logger.warning(f"[{analysis_id}] Validation failed: {validation_error}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "Validation error",
                    "message": validation_error
                }
            )

        # Cache HIT (on ne met pas en cache si lap_filter différent selon les cas; clé = filename seulement)
        # Pas d'incrément du compteur sur cache hit (analyse déjà comptée précédemment).
        if redis and not lap_list:
            cached_raw = await redis.get(f"{REDIS_KEY_PREFIX}{cache_key}")
            if cached_raw:
                logger.info(f"[{analysis_id}] Redis cache HIT")
                data = json.loads(cached_raw)
                # Sanitize loaded data for JSON compliance (NaN/Inf -> None)
                sanitized = sanitize_json_data(data)
                return JSONResponse(content={"cached": True, "cache_key": cache_key, **sanitized})

        # Analyse (cache MISS)
        if redis and not lap_list:
            logger.info(f"[{analysis_id}] Redis cache MISS")
        service = AnalysisService(lap_filter=lap_list if lap_list else None)
        result = await service.process_telemetry(
            file, analysis_id,
            track_condition=cond,
            track_temperature=temp_c,
            session_name=session_name,
        )

        # Stocker en cache (uniquement analyse complète sans filtre de tours)
        if redis and not lap_list:
            sanitized_for_cache = sanitize_json_data(result)
            await redis.setex(
                f"{REDIS_KEY_PREFIX}{cache_key}",
                REDIS_CACHE_TTL,
                json.dumps(sanitized_for_cache, default=str)
            )

        if user_id:
            increment_analysis_count(user_id)

        logger.info(f"[{analysis_id}] ✅ Analysis completed successfully")
        resp = AnalysisResponse(**result)
        content = {"cache_key": cache_key, **resp.model_dump()}
        sanitized_content = sanitize_json_data(content)
        return JSONResponse(content=sanitized_content)
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"[{analysis_id}] ❌ ValueError: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Processing error",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"[{analysis_id}] ❌ Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Internal server error",
                "message": "Une erreur s'est produite lors de l'analyse. Veuillez réessayer."
            }
        )


@router.get(
    "/analyse/{cache_key}",
    summary="Récupérer une analyse depuis le cache",
    description="Retourne le résultat d'une analyse par cache_key (md5 du filename)"
)
async def get_analyse_by_id(request: Request, cache_key: str):
    """Récupérer une analyse depuis le cache Redis."""
    redis = getattr(request.app.state, "redis", None)
    if not redis:
        raise HTTPException(status_code=503, detail="Cache non disponible")
    cached_raw = await redis.get(f"{REDIS_KEY_PREFIX}{cache_key}")
    if not cached_raw:
        raise HTTPException(status_code=404, detail="Analyse non trouvée ou expirée")
    data = json.loads(cached_raw)
    return JSONResponse(content={"cached": True, "cache_key": cache_key, **data})


@router.get(
    "/status/{analysis_id}",
    summary="Statut d'une analyse",
    description="Vérifier le statut d'une analyse (pour futures implémentations async)"
)
async def get_analysis_status(analysis_id: str):
    """
    Vérifier le statut d'une analyse.
    
    Args:
        analysis_id: ID de l'analyse
    
    Returns:
        Statut de l'analyse
    """
    # TODO: Implémenter avec cache/DB pour analyses async
    return {
        "analysis_id": analysis_id,
        "status": "completed",
        "message": "Analyse synchrone (toujours completed)"
    }


@router.post("/process-video")
async def process_video(file: UploadFile = File(...)):
    """
    Traite une vidéo MP4 avec l'API Grok pour transcription et analyse.
    
    Args:
        file: Fichier vidéo MP4 uploadé
    
    Returns:
        {
            "filename": str,
            "summary": str,
            "status": "processed"
        }
    """
    try:
        # Validation du format
        if not file.filename or not file.filename.lower().endswith('.mp4'):
            return JSONResponse(
                status_code=400,
                content={"error": "MP4 only"}
            )
        
        logger.info(f"🎥 Video upload: {file.filename}")
        print(f"🎥 Processing video: {file.filename}")
        
        # Créer le dossier temp s'il n'existe pas
        temp_dir = Path(settings.TEMP_DIR)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Sauvegarde temporaire
        temp_path = temp_dir / file.filename
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"✅ Video saved to: {temp_path}")
        print(f"✅ Video saved: {temp_path}")
        
        # 2. MOCK IA (Gratuit - Pas de paiement)
        if os.getenv("MOCK_VIDEO_AI", "true").lower() == "true":
            logger.info("🤖 Using MOCK Video AI (free)")
            print(f"🤖 MOCK IA Analysis for: {file.filename}")
            return JSONResponse(content={
                "filename": file.filename,
                "summary": settings.MOCK_SUMMARY.strip(),
                "tags": ["business", "startup", "pitch"],
                "status": "pro_analyzed"
            })
        
        # 3. GROK API (transcription + analyse) - Fallback si MOCK désactivé
        try:
            import httpx
            
            grok_api_key = settings.GROK_API_KEY or os.getenv("GROK_API_KEY", "")
            if not grok_api_key:
                logger.warning("GROK_API_KEY not configured, skipping Grok analysis")
                return JSONResponse(content={
                    "filename": file.filename,
                    "summary": "Grok API not configured. Video saved but not analyzed.",
                    "status": "saved",
                    "temp_path": str(temp_path)
                })
            
            # Appel à l'API Grok
            grok_url = f"{settings.GROK_API_URL}/chat/completions"
            prompt = f"Analyse cette vidéo karting et donne un résumé: {file.filename}"
            
            logger.info(f"🤖 Calling Grok API...")
            print(f"🤖 Calling Grok API for: {file.filename}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    grok_url,
                    headers={
                        "Authorization": f"Bearer {grok_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "grok-beta",
                        "messages": [
                            {"role": "user", "content": prompt}
                        ]
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    grok_data = response.json()
                    summary = grok_data.get("choices", [{}])[0].get("message", {}).get("content", "Analysis completed")
                    
                    logger.info(f"✅ Grok analysis completed")
                    print(f"✅ Grok analysis completed for: {file.filename}")
                    
                    return JSONResponse(content={
                        "filename": file.filename,
                        "summary": summary,
                        "status": "processed"
                    })
                else:
                    error_msg = f"Grok API error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    print(f"❌ {error_msg}")
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": error_msg,
                            "filename": file.filename,
                            "status": "error"
                        }
                    )
        
        except ImportError:
            logger.warning("httpx not installed, skipping Grok API call")
            return JSONResponse(content={
                "filename": file.filename,
                "summary": "Grok API client not available. Install httpx for Grok integration.",
                "status": "saved",
                "temp_path": str(temp_path)
            })
        except Exception as grok_error:
            logger.error(f"Grok API error: {grok_error}", exc_info=True)
            print(f"❌ Grok API error: {grok_error}")
            return JSONResponse(content={
                "filename": file.filename,
                "summary": f"Video saved but Grok analysis failed: {str(grok_error)}",
                "status": "partial",
                "temp_path": str(temp_path)
            })
    
    except Exception as e:
        error_msg = f"Error processing video: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(f"❌ {error_msg}")
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )
