#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API Utilities
Utilitaires pour l'API REST
"""

import os
import logging
from typing import Optional
from fastapi import UploadFile

from .config import settings

logger = logging.getLogger(__name__)


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
