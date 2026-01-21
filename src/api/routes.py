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
