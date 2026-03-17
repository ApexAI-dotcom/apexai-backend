#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API Utilities
Utilitaires pour l'API REST
"""

import os
import logging
import math
import numpy as np
from typing import Optional, Any, Dict, List
from fastapi import UploadFile

from .config import settings

logger = logging.getLogger(__name__)


def sanitize_json_data(obj: Any) -> Any:
    """
    Recursively replaces NaN, Infinity, -Infinity with None for JSON compliance.
    Also handles numpy types and other non-standard JSON types.
    """
    if isinstance(obj, dict):
        return {k: sanitize_json_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json_data(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return [sanitize_json_data(x) for x in obj.tolist()]
    elif hasattr(obj, "isoformat"):  # datetime/date
        return obj.isoformat()
    else:
        return obj


async def validate_csv_file(file: UploadFile) -> Optional[str]:
    """
    Valider un fichier CSV.
    
    Args:
        file: Fichier uploadé
    
    Returns:
        None si OK, sinon message d'erreur
    """
    try:
        # Vérifier extension
        if not file.filename:
            return "Nom de fichier manquant"
        
        ext = os.path.splitext(file.filename.lower())[1]
        if ext != '.csv':
            return f"Extension invalide. Attendu: .csv, reçu: {ext}"
        
        # Lire contenu
        content = await file.read()
        size = len(content)
        
        # Reset pour lecture ultérieure
        await file.seek(0)
        
        # Vérifier taille
        if size > settings.MAX_FILE_SIZE_BYTES:
            size_mb = size / (1024 * 1024)
            return f"Fichier trop gros ({size_mb:.1f}MB). Max: {settings.MAX_FILE_SIZE_MB}MB"
        
        if size < 1000:
            return "Fichier trop petit (<1KB). Vérifiez que c'est un CSV valide."
        
        # Vérifier encoding et contenu
        try:
            sample = content[:5000].decode('utf-8')
        except UnicodeDecodeError:
            try:
                sample = content[:5000].decode('latin-1')
            except UnicodeDecodeError:
                return "Fichier corrompu (encoding invalide). Utilisez UTF-8 ou Latin-1."
        
        # Vérifier présence de colonnes GPS (heuristique basique)
        sample_lower = sample.lower()
        has_gps = (
            'latitude' in sample_lower or 'lat' in sample_lower or
            'longitude' in sample_lower or 'lon' in sample_lower or
            'gps' in sample_lower
        )
        
        if not has_gps:
            return "Colonnes GPS non détectées. Le fichier doit contenir Latitude/Longitude."
        
        return None  # Validation OK
    
    except Exception as e:
        logger.error(f"Error validating file: {str(e)}", exc_info=True)
        return f"Erreur de validation: {str(e)}"
