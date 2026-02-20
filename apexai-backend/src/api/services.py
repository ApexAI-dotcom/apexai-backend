#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API Services
Service d'analyse de télémétrie
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from fastapi import UploadFile

from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter
from src.analysis.geometry import (
    calculate_trajectory_geometry,
    detect_laps,
    detect_corners,
    calculate_optimal_trajectory
)
from src.analysis.scoring import calculate_performance_score
from src.analysis.coaching import generate_coaching_advice
from src.analysis.performance_metrics import analyze_corner_performance
from src.visualization.visualization import generate_all_plots_base64

from .config import settings
from .models import (
    AnalysisResponse, PerformanceScore, ScoreBreakdown,
    CornerAnalysis, CoachingAdvice, PlotUrls, Statistics
)

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service d'analyse de télémétrie"""
    
    def __init__(self):
        """Initialiser le service"""
        os.makedirs(settings.TEMP_DIR, exist_ok=True)
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    
    async def process_telemetry(
        self,
        file: UploadFile,
        analysis_id: str
    ) -> Dict[str, Any]:
        """
        Traiter un fichier de télémétrie complet.
        
        Args:
            file: Fichier CSV uploadé
            analysis_id: ID unique de l'analyse
        
        Returns:
            Dictionnaire avec résultats de l'analyse
        """
        start_time = datetime.now()
        temp_path = None
        
        try:
            # 1. Sauvegarder fichier temporairement
            temp_path = os.path.join(
                settings.TEMP_DIR,
                f"{analysis_id}_{file.filename}"
            )
            
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            logger.info(f"[{analysis_id}] File saved: {len(content)} bytes - {file.filename}")
            
            # Extraire les Beacon Markers AiM/MoTeC depuis le fichier brut
            beacon_markers = []
            try:
                with open(temp_path, 'r', encoding='utf-8', errors='ignore') as bfile:
                    for i, bline in enumerate(bfile):
                        if i > 20:
                            break
                        if 'Beacon' in bline or 'beacon' in bline:
                            parts = bline.strip().replace('"', '').split(',')
                            if len(parts) >= 2:
                                raw = parts[1].strip()
                                parsed = []
                                for tok in raw.split():
                                    try:
                                        parsed.append(float(tok))
                                    except ValueError:
                                        pass
                                if parsed:
                                    beacon_markers = sorted(parsed)
                                    break
            except Exception as be:
                logger.warning(f"[{analysis_id}] Could not read beacon markers: {be}")
            
            if beacon_markers:
                logger.info(f"[{analysis_id}] ✓ Beacon Markers: {len(beacon_markers)} passages, "
                           f"1er beacon à t={beacon_markers[0]:.3f}s")
            else:
                logger.warning(f"[{analysis_id}] ⚠️ Pas de Beacon Markers dans ce fichier")
            
            # 2. Pipeline d'analyse
            logger.info(f"[{analysis_id}] Step 1/5: Loading data...")
            result = robust_load_telemetry(temp_path)
            
            if not result['success']:
                raise ValueError(f"Échec chargement: {result.get('error', 'Unknown error')}")
            
            df = result['data']
            logger.info(f"[{analysis_id}] Loaded {len(df)} rows")
            
            # Injecter les beacons AVANT detect_laps (appelé à Step 3.5)
            if beacon_markers:
                df.attrs['beacon_markers'] = beacon_markers
            
            logger.info(f"[{analysis_id}] Step 2/5: Filtering GPS...")
            df = apply_savgol_filter(df)
            
            logger.info(f"[{analysis_id}] Step 3/5: Calculating geometry...")
            df = calculate_trajectory_geometry(df)
            
            logger.info(f"[{analysis_id}] Step 3.5/5: Detecting laps...")
            df = detect_laps(df)
            
            logger.info(f"[{analysis_id}] Step 4/5: Detecting corners...")
            df = detect_corners(df, min_lateral_g=0.08)
            
            corners_meta = df.attrs.get('corners', {})
            corner_details = corners_meta.get('corner_details', [])
            
            logger.info(f"[{analysis_id}] Detected {len(corner_details)} corners")
            
            # Calcul trajectoire optimale
            df = calculate_optimal_trajectory(df)
            
            # 3. Scoring
            logger.info(f"[{analysis_id}] Step 5/5: Calculating score and coaching...")
            score_data = calculate_performance_score(df, corner_details)
            
            # Analyse par virage avec gestion d'erreurs robuste
            def sanitize_corner_data(corner_data: Dict[str, Any]) -> Dict[str, Any]:
                """
                Nettoyer et mapper les données de virage pour Pydantic.
                Extrait les données de 'metrics' et les met au niveau racine.
                """
                try:
                    # Extraire metrics si présent
                    metrics = corner_data.get('metrics', {})
                    
                    # Construire dictionnaire nettoyé
                    sanitized = {
                        'corner_id': int(corner_data.get('corner_id', 0)),
                        'corner_number': int(corner_data.get('corner_number', corner_data.get('corner_id', 0))),
                        'corner_type': str(corner_data.get('corner_type', 'unknown')),
                        
                        # Vitesses (depuis metrics ou corner_data)
                        'apex_speed_real': float(metrics.get('apex_speed_real', corner_data.get('apex_speed_kmh', 0.0))) if metrics.get('apex_speed_real') is not None else float(corner_data.get('apex_speed_kmh', 0.0)),
                        'apex_speed_optimal': float(metrics.get('apex_speed_optimal', corner_data.get('optimal_apex_speed_kmh', 0.0))) if metrics.get('apex_speed_optimal') is not None else float(corner_data.get('optimal_apex_speed_kmh', 0.0)),
                        'speed_efficiency': float(metrics.get('speed_efficiency', 0.0)) if metrics.get('speed_efficiency') is not None else 0.0,
                        
                        # Erreurs apex
                        'apex_distance_error': float(metrics.get('apex_distance_error', 0.0)) if metrics.get('apex_distance_error') is not None else 0.0,
                        'apex_direction_error': str(metrics.get('apex_direction_error', 'center')) if metrics.get('apex_direction_error') is not None else 'center',
                        
                        # G latéral et temps
                        'lateral_g_max': float(metrics.get('lateral_g_max', corner_data.get('max_lateral_g', 0.0))) if metrics.get('lateral_g_max') is not None else float(corner_data.get('max_lateral_g', 0.0)),
                        'time_lost': float(metrics.get('time_lost', 0.0)) if metrics.get('time_lost') is not None else 0.0,
                        
                        # Score et grade
                        'grade': str(corner_data.get('grade', 'C')),
                        'score': float(corner_data.get('score', 50.0)) if corner_data.get('score') is not None else 50.0
                    }
                    
                    return sanitized
                    
                except Exception as e:
                    logger.warning(f"[{analysis_id}] Error sanitizing corner data: {e}")
                    # Retourner valeurs par défaut
                    return {
                        'corner_id': int(corner_data.get('corner_id', 0)),
                        'corner_number': int(corner_data.get('corner_id', 0)),
                        'corner_type': str(corner_data.get('corner_type', 'unknown')),
                        'apex_speed_real': 0.0,
                        'apex_speed_optimal': 0.0,
                        'speed_efficiency': 0.0,
                        'apex_distance_error': 0.0,
                        'apex_direction_error': 'center',
                        'lateral_g_max': 0.0,
                        'time_lost': 0.0,
                        'grade': 'C',
                        'score': 50.0
                    }
            
            # Analyser chaque virage avec gestion d'erreurs
            logger.info(f"[{analysis_id}] Analyzing corner performance...")
            corner_analysis_list = []
            
            for corner in corner_details:
                try:
                    analysis = analyze_corner_performance(df, corner)
                    # Nettoyer les données
                    sanitized = sanitize_corner_data(analysis)
                    corner_analysis_list.append(sanitized)
                except Exception as e:
                    logger.warning(f"[{analysis_id}] Failed to analyze corner {corner.get('id', 'unknown')}: {e}")
                    # Ajouter un placeholder avec données minimales
                    placeholder = {
                        'corner_id': int(corner.get('id', len(corner_analysis_list) + 1)),
                        'corner_number': int(corner.get('id', len(corner_analysis_list) + 1)),
                        'corner_type': str(corner.get('type', 'unknown')),
                        'apex_speed_real': 0.0,
                        'apex_speed_optimal': 0.0,
                        'speed_efficiency': 0.0,
                        'apex_distance_error': 0.0,
                        'apex_direction_error': 'center',
                        'lateral_g_max': 0.0,
                        'time_lost': 0.0,
                        'grade': 'C',
                        'score': 50.0
                    }
                    corner_analysis_list.append(placeholder)
            
            logger.info(f"[{analysis_id}] {len(corner_analysis_list)} corners analyzed successfully")
            
            # Coaching (peut échouer si corner_analysis_list est vide, donc try/except)
            try:
                coaching_advice_list = generate_coaching_advice(
                    df, corner_details, score_data, corner_analysis_list
                )
            except Exception as e:
                logger.warning(f"[{analysis_id}] Failed to generate coaching advice: {e}")
                coaching_advice_list = []
            
            # 4. Graphiques en base64 (pas de fichiers disque)
            logger.info(f"[{analysis_id}] Generating plots...")
            import base64
            import io
            
            plots_b64 = generate_all_plots_base64(df)
            plots_urls = plots_b64  # base64 data URIs
            
            # 5. Construire réponse
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Temps du tour
            lap_time = 0.0
            if 'time' in df.columns and len(df) > 0:
                time_values = df['time'].dropna()
                if len(time_values) > 0:
                    lap_time = float(time_values.iloc[-1] - time_values.iloc[0])
            
            logger.info(f"[{analysis_id}] ✅ Completed in {processing_time:.2f}s")
            
            # Construire réponse avec modèles Pydantic
            response = AnalysisResponse(
                success=True,
                analysis_id=analysis_id,
                timestamp=datetime.now(),
                corners_detected=len(corner_details),
                lap_time=lap_time,
                performance_score=PerformanceScore(
                    overall_score=float(score_data.get('overall_score', 0.0)),
                    grade=str(score_data.get('grade', 'C')),
                    breakdown=ScoreBreakdown(**score_data.get('breakdown', {
                        'apex_precision': 0.0,
                        'trajectory_consistency': 0.0,
                        'apex_speed': 0.0,
                        'sector_times': 0.0
                    })),
                    percentile=score_data.get('percentile', 78)
                ),
                corner_analysis=[
                    CornerAnalysis(**corner_analysis)
                    for corner_analysis in corner_analysis_list[:10]  # Top 10
                    if corner_analysis  # Filtrer les None/empty
                ],
                coaching_advice=[
                    CoachingAdvice(**advice)
                    for advice in coaching_advice_list[:5]  # Top 5
                    if advice and isinstance(advice, dict)  # Filtrer les None/invalid
                ],
                plots=PlotUrls(**plots_urls),
                statistics=Statistics(
                    processing_time_seconds=processing_time,
                    data_points=int(len(df)),
                    best_corners=score_data.get('details', {}).get('best_corners', [])[:3],
                    worst_corners=score_data.get('details', {}).get('worst_corners', [])[:3],
                    avg_apex_distance=float(score_data.get('details', {}).get('avg_apex_distance', 0.0)),
                    avg_apex_speed_efficiency=float(score_data.get('details', {}).get('avg_apex_speed_efficiency', 0.0))
                )
            )
            
            # Convertir en dict pour JSON serialization
            return response.dict(exclude_none=True)
            
        except Exception as e:
            logger.error(f"[{analysis_id}] ❌ Analysis failed: {str(e)}", exc_info=True)
            raise
        
        finally:
            # Nettoyage fichier temporaire
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.info(f"[{analysis_id}] Cleaned up temp file")
                except Exception as e:
                    logger.warning(f"[{analysis_id}] Failed to cleanup temp file: {str(e)}")
