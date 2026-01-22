#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API Routes
Endpoints de l'API REST
"""

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import logging
import uuid
import os
import tempfile
from pathlib import Path

from .models import AnalysisResponse, ErrorResponse
from .services import AnalysisService
from .utils import validate_csv_file
from .config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Erreur de validation"},
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
    - Taille max : 20 MB
    - Format : CSV uniquement
    - Colonnes requises : Latitude, Longitude, Speed
    """
)
async def analyze_telemetry(
    file: UploadFile = File(..., description="Fichier CSV de télémétrie")
) -> AnalysisResponse:
    """
    Analyser un fichier de télémétrie.
    
    Args:
        file: Fichier CSV uploadé
    
    Returns:
        AnalysisResponse avec résultats complets
    """
    analysis_id = str(uuid.uuid4())[:8]
    logger.info(f"🏁 New analysis request: {analysis_id} - {file.filename}")
    
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
        
        # Analyse
        service = AnalysisService()
        result = await service.process_telemetry(file, analysis_id)
        
        logger.info(f"[{analysis_id}] ✅ Analysis completed successfully")
        # result est déjà un dict depuis services.py
        return AnalysisResponse(**result)
        
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
