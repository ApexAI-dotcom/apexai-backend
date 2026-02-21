#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API Services
Service d'analyse de télémétrie
"""

import asyncio
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


def _run_analysis_pipeline_sync(
    temp_path: str,
    beacon_markers: list,
    analysis_id: str,
    start_time: datetime,
) -> Dict[str, Any]:
    """Pipeline d'analyse synchrone (exécuté dans un thread pour ne pas bloquer l'event loop)."""
    logger.info(f"[{analysis_id}] Step 1/5: Loading data...")
    result = robust_load_telemetry(temp_path)
    if not result["success"]:
        raise ValueError(f"Échec chargement: {result.get('error', 'Unknown error')}")

    df = result["data"]
    logger.info(f"[{analysis_id}] Loaded {len(df)} rows")

    if beacon_markers:
        df.attrs["beacon_markers"] = beacon_markers

    logger.info(f"[{analysis_id}] Step 2/5: Filtering GPS...")
    df = apply_savgol_filter(df)
    logger.info(f"[{analysis_id}] Step 3/5: Calculating geometry...")
    df = calculate_trajectory_geometry(df)
    logger.info(f"[{analysis_id}] Step 3.5/5: Detecting laps...")
    df = detect_laps(df)
    logger.info(f"[{analysis_id}] Step 4/5: Detecting corners...")
    df = detect_corners(df, min_lateral_g=0.25)

    corners_meta = df.attrs.get("corners", {})
    corner_details = corners_meta.get("corner_details", [])
    logger.info(f"[{analysis_id}] Detected {len(corner_details)} corners")

    df = calculate_optimal_trajectory(df)
    logger.info(f"[{analysis_id}] Step 5/5: Calculating score and coaching...")
    score_data = calculate_performance_score(df, corner_details)

    def sanitize_corner_data(corner_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            metrics = corner_data.get("metrics", {})
            return {
                "corner_id": int(corner_data.get("corner_id", 0)),
                "corner_number": int(corner_data.get("corner_number", corner_data.get("corner_id", 0))),
                "corner_type": str(corner_data.get("corner_type", "unknown")),
                "apex_speed_real": float(metrics.get("apex_speed_real", corner_data.get("apex_speed_kmh", 0.0)) or corner_data.get("apex_speed_kmh", 0.0)),
                "apex_speed_optimal": float(metrics.get("apex_speed_optimal", corner_data.get("optimal_apex_speed_kmh", 0.0)) or corner_data.get("optimal_apex_speed_kmh", 0.0)),
                "speed_efficiency": float(metrics.get("speed_efficiency", 0.0) or 0.0),
                "apex_distance_error": float(metrics.get("apex_distance_error", 0.0) or 0.0),
                "apex_direction_error": str(metrics.get("apex_direction_error", "center") or "center"),
                "lateral_g_max": float(metrics.get("lateral_g_max", corner_data.get("max_lateral_g", 0.0)) or corner_data.get("max_lateral_g", 0.0)),
                "time_lost": float(metrics.get("time_lost", 0.0) or 0.0),
                "grade": str(corner_data.get("grade", "C")),
                "score": float(corner_data.get("score", 50.0) or 50.0),
                "apex_lat": corner_data.get("apex_lat"),
                "apex_lon": corner_data.get("apex_lon"),
            }
        except Exception as e:
            logger.warning(f"[{analysis_id}] Error sanitizing corner data: {e}")
            return {
                "corner_id": int(corner_data.get("corner_id", 0)),
                "corner_number": int(corner_data.get("corner_id", 0)),
                "corner_type": str(corner_data.get("corner_type", "unknown")),
                "apex_speed_real": 0.0,
                "apex_speed_optimal": 0.0,
                "speed_efficiency": 0.0,
                "apex_distance_error": 0.0,
                "apex_direction_error": "center",
                "lateral_g_max": 0.0,
                "time_lost": 0.0,
                "grade": "C",
                "score": 50.0,
                "apex_lat": None,
                "apex_lon": None,
            }

    logger.info(f"[{analysis_id}] Analyzing corner performance...")
    corner_analysis_list = []
    for corner in corner_details:
        try:
            analysis = analyze_corner_performance(df, corner)
            corner_analysis_list.append(sanitize_corner_data(analysis))
        except Exception as e:
            logger.warning(f"[{analysis_id}] Failed to analyze corner {corner.get('id', 'unknown')}: {e}")
            corner_analysis_list.append({
                "corner_id": int(corner.get("id", len(corner_analysis_list) + 1)),
                "corner_number": int(corner.get("id", len(corner_analysis_list) + 1)),
                "corner_type": str(corner.get("type", "unknown")),
                "apex_speed_real": 0.0,
                "apex_speed_optimal": 0.0,
                "speed_efficiency": 0.0,
                "apex_distance_error": 0.0,
                "apex_direction_error": "center",
                "lateral_g_max": 0.0,
                "time_lost": 0.0,
                "grade": "C",
                "score": 50.0,
                "apex_lat": None,
                "apex_lon": None,
            })

    logger.info(f"[{analysis_id}] {len(corner_analysis_list)} corners analyzed successfully")

    # Virages uniques du circuit (dédupliquer par corner_id)
    unique_by_id = {}
    for c in corner_analysis_list:
        cid = c.get("corner_id")
        if cid is not None and cid not in unique_by_id:
            unique_by_id[cid] = c
    unique_corner_analysis = list(unique_by_id.values())
    corners_detected = len(unique_corner_analysis)

    # Score global = moyenne des scores virages (cohérent avec affichage)
    corner_scores = [float(c.get("score", 50)) for c in unique_corner_analysis if c.get("score") is not None]
    if corner_scores:
        score_data["overall_score"] = round(sum(corner_scores) / len(corner_scores), 1)
        s = score_data["overall_score"]
        if s >= 80:
            score_data["grade"] = "A"
        elif s >= 70:
            score_data["grade"] = "B"
        elif s >= 55:
            score_data["grade"] = "C"
        elif s >= 40:
            score_data["grade"] = "D"
        else:
            score_data["grade"] = "F"

    try:
        coaching_advice_list = generate_coaching_advice(
            df, corner_details, score_data, unique_corner_analysis
        )
    except Exception as e:
        logger.warning(f"[{analysis_id}] Failed to generate coaching advice: {e}")
        coaching_advice_list = []

    logger.info(f"[{analysis_id}] Generating plots...")
    df.attrs["corner_analysis"] = unique_corner_analysis
    plots_urls = generate_all_plots_base64(df)

    processing_time = (datetime.now() - start_time).total_seconds()

    # Meilleur tour depuis beacon markers (pas durée session)
    if beacon_markers and len(beacon_markers) >= 2:
        lap_times_list = [beacon_markers[0]]
        for i in range(1, len(beacon_markers)):
            lap_times_list.append(beacon_markers[i] - beacon_markers[i - 1])
        timed_laps = lap_times_list[1:] if len(lap_times_list) > 1 else lap_times_list
        best_lap_time = round(min(timed_laps), 3)
        avg_lap_time = round(sum(timed_laps) / len(timed_laps), 3) if timed_laps else best_lap_time
        logger.info(
            f"[{analysis_id}] Meilleur tour: {best_lap_time}s, "
            f"Moyenne: {avg_lap_time}s sur {len(timed_laps)} tours"
        )
        lap_time = best_lap_time
    else:
        if "time" in df.columns and len(df) > 0:
            time_values = df["time"].dropna()
            if len(time_values) > 0:
                lap_time = round(float(time_values.iloc[-1] - time_values.iloc[0]), 3)
            else:
                lap_time = 0.0
        else:
            lap_time = 0.0

    logger.info(f"[{analysis_id}] ✅ Completed in {processing_time:.2f}s")

    response = AnalysisResponse(
        success=True,
        analysis_id=analysis_id,
        timestamp=datetime.now(),
        corners_detected=corners_detected,
        lap_time=lap_time,
        performance_score=PerformanceScore(
            overall_score=float(score_data.get("overall_score", 0.0)),
            grade=str(score_data.get("grade", "C")),
            breakdown=ScoreBreakdown(**score_data.get("breakdown", {
                "apex_precision": 0.0,
                "trajectory_consistency": 0.0,
                "apex_speed": 0.0,
                "sector_times": 0.0,
            })),
            percentile=score_data.get("percentile", 78),
        ),
        corner_analysis=[
            CornerAnalysis(**c) for c in unique_corner_analysis if c
        ],
        coaching_advice=[
            CoachingAdvice(**a) for a in coaching_advice_list[:5]
            if a and isinstance(a, dict)
        ],
        plots=PlotUrls(**plots_urls),
        statistics=Statistics(
            processing_time_seconds=processing_time,
            data_points=int(len(df)),
            best_corners=score_data.get("details", {}).get("best_corners", [])[:3],
            worst_corners=score_data.get("details", {}).get("worst_corners", [])[:3],
            avg_apex_distance=float(score_data.get("details", {}).get("avg_apex_distance", 0.0)),
            avg_apex_speed_efficiency=float(score_data.get("details", {}).get("avg_apex_speed_efficiency", 0.0)),
        ),
    )
    return response.dict(exclude_none=True)


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
            
            content = await file.read()
            MAX_SIZE = 50 * 1024 * 1024  # 50MB
            if len(content) > MAX_SIZE:
                raise ValueError(
                    f"Fichier trop volumineux ({len(content)/1024/1024:.1f}MB). Limite : 50MB."
                )
            with open(temp_path, "wb") as f:
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
            
            # Pipeline d'analyse en thread pour ne pas bloquer l'event loop (évite timeout 30s)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                _run_analysis_pipeline_sync,
                temp_path,
                beacon_markers,
                analysis_id,
                start_time,
            )
            return result
            
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
