#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API Services
Service d'analyse de télémétrie
"""

import asyncio
import os
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import UploadFile
import numpy as np
import pandas as pd

from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter
from src.analysis.geometry import (
    calculate_trajectory_geometry,
    detect_laps,
    detect_corners,
    calculate_optimal_trajectory
)
from src.analysis.scoring import calculate_performance_score, validate_score_consistency
from src.analysis.coaching import generate_coaching_advice
from src.analysis.performance_metrics import analyze_corner_performance
from src.visualization.visualization import generate_all_plots_base64, generate_plot_data

from .config import settings
from .models import (
    AnalysisResponse, PerformanceScore, ScoreBreakdown,
    CornerAnalysis, CoachingAdvice, PlotUrls, Statistics, SessionConditions
)

logger = logging.getLogger(__name__)

BUFFER_BEFORE_AFTER = 75
BUFFER_BETWEEN_GROUPS = 50


def _filter_laps_with_buffer(
    df: "pd.DataFrame",
    lap_filter: List[int],
    analysis_id: str,
) -> "pd.DataFrame":
    """
    Filtre le dataframe aux tours sélectionnés en ajoutant des buffers pour préserver
    la géométrie (éviter de tronquer en bordure de tour et casser la détection des virages).
    - 75 points avant le premier point du premier tour et après le dernier point du dernier tour.
    - 50 points de buffer entre chaque groupe de tours non contigus (ex. entre tour 2 et tour 5).
    """
    if not lap_filter or "lap_number" not in df.columns:
        return df[df["lap_number"].isin(lap_filter)].reset_index(drop=True) if lap_filter else df
    n = len(df)
    laps_sorted = sorted(set(lap_filter))
    positions_to_keep = set()
    prev_end = -1
    for i, lap in enumerate(laps_sorted):
        pos = np.where(df["lap_number"].values == lap)[0]
        if len(pos) == 0:
            continue
        mi, ma = int(pos.min()), int(pos.max())
        if i == 0:
            start_buf = max(0, mi - BUFFER_BEFORE_AFTER)
            end_buf = ma + BUFFER_BETWEEN_GROUPS if len(laps_sorted) > 1 else min(n - 1, ma + BUFFER_BEFORE_AFTER)
            positions_to_keep.update(range(start_buf, end_buf + 1))
        elif i == len(laps_sorted) - 1:
            if lap - laps_sorted[i - 1] > 1:
                gap_start = max(0, prev_end + 1)
                gap_end = min(n - 1, prev_end + BUFFER_BETWEEN_GROUPS)
                positions_to_keep.update(range(gap_start, gap_end + 1))
                positions_to_keep.update(range(max(0, mi - BUFFER_BETWEEN_GROUPS), mi))
            end_buf = min(n - 1, ma + BUFFER_BEFORE_AFTER)
            positions_to_keep.update(range(max(0, mi - BUFFER_BETWEEN_GROUPS), end_buf + 1))
        else:
            if lap - laps_sorted[i - 1] > 1:
                positions_to_keep.update(range(max(0, prev_end + 1), min(n, prev_end + BUFFER_BETWEEN_GROUPS + 1)))
                positions_to_keep.update(range(max(0, mi - BUFFER_BETWEEN_GROUPS), mi))
            positions_to_keep.update(range(mi, ma + 1))
        prev_end = ma
    pos_sorted = sorted(positions_to_keep)
    if not pos_sorted:
        return df[df["lap_number"].isin(lap_filter)].reset_index(drop=True)
    return df.iloc[pos_sorted].reset_index(drop=True)


def _parse_laps_sync(temp_path: str, beacon_markers: list) -> List[Dict[str, Any]]:
    """
    Charge le CSV, détecte les tours (réutilise load + savgol + geometry + detect_laps),
    retourne la liste des tours avec lap_number, lap_time_seconds, points_count, is_outlier.
    is_outlier = True si temps > 1.5 * médiane (tours stand / prépa).
    """
    result = robust_load_telemetry(temp_path)
    if not result["success"]:
        raise ValueError(result.get("error", "Échec chargement"))

    df = result["data"]
    if beacon_markers:
        df.attrs["beacon_markers"] = beacon_markers
    df = apply_savgol_filter(df)
    df = calculate_trajectory_geometry(df)
    df = detect_laps(df)

    if "lap_number" not in df.columns:
        return [{"lap_number": 1, "lap_time_seconds": 0.0, "points_count": len(df), "is_outlier": False}]

    time_col = "time" if "time" in df.columns else None
    laps_out = []

    for lap_num, group in df.groupby("lap_number", sort=True):
        lap_num = int(lap_num)
        points_count = int(len(group))
        if time_col and group[time_col].notna().any():
            t = pd.to_numeric(group[time_col], errors="coerce").dropna()
            lap_time_seconds = float(t.max() - t.min()) if len(t) >= 2 else 0.0
        else:
            lap_time_seconds = 0.0
        laps_out.append({
            "lap_number": lap_num,
            "lap_time_seconds": round(lap_time_seconds, 3),
            "points_count": points_count,
            "is_outlier": False,
        })

    if not laps_out:
        return laps_out

    # Médiane des temps (tours avec temps > 0 et lap_number >= 1)
    times_for_median = [x["lap_time_seconds"] for x in laps_out if x["lap_time_seconds"] > 0 and x["lap_number"] >= 1]
    if times_for_median:
        median_time = float(np.median(times_for_median))
        points_for_median = [x["points_count"] for x in laps_out if x["lap_number"] >= 1]
        median_points = float(np.median(points_for_median)) if points_for_median else float("inf")
        threshold = 1.5 * median_time
        
        for lap in laps_out:
            if lap["lap_number"] == 0:
                lap["is_outlier"] = True
            elif lap["lap_time_seconds"] > threshold:
                lap["is_outlier"] = True
            # In-lap / Cool-down court : si le tour est 15% plus lent que la médiane
            elif lap["lap_time_seconds"] > 1.15 * median_time:
                lap["is_outlier"] = True
            elif lap["lap_number"] == laps_out[-1]["lap_number"] and lap["points_count"] < 0.8 * median_points:
                lap["is_outlier"] = True
    else:
        for lap in laps_out:
            if lap["lap_number"] == 0:
                lap["is_outlier"] = True

    return laps_out


def _run_analysis_pipeline_sync(
    temp_path: str,
    beacon_markers: list,
    analysis_id: str,
    start_time: datetime,
    lap_filter: Optional[List[int]] = None,
    track_condition: str = "dry",
    track_temperature: Optional[float] = None,
    session_name: Optional[str] = None,
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
    laps_analyzed = 1
    # Calculer curvature threshold sur FULL TRACK (avant filtrage) pour stabilité entre sélections de tours
    curvature_threshold_global = None
    if "curvature" in df.columns and "lap_number" in df.columns:
        df_circuit = df[df["lap_number"] >= 1]
        if len(df_circuit) >= 50:
            curv = np.nan_to_num(pd.to_numeric(df_circuit["curvature"], errors="coerce").values, nan=0.0, posinf=0.0, neginf=0.0)
            curv_abs = np.abs(curv)
            nonzero = curv_abs[curv_abs > 1e-6]
            if len(nonzero) > 0:
                curvature_threshold_global = float(np.percentile(nonzero, 25))
                logger.info(f"[DIAG] GLOBAL curvature threshold (full track): {curvature_threshold_global:.6f}")
    if "lap_number" in df.columns:
        laps_available = sorted(df["lap_number"].dropna().unique().astype(int).tolist())
        logger.info(f"[DIAG] Tours disponibles (lap_number): {laps_available}")
    
    # We always analyze the full session now, ignoring lap_filter for the initial df reduction
    if "lap_number" in df.columns:
        laps_analyzed = int(df["lap_number"].nunique())
    
    logger.info(f"[DIAG] Appel detect_corners avec {len(df)} rows, laps_analyzed={laps_analyzed}")
    logger.info(f"[{analysis_id}] Step 4/5: Detecting corners...")
    df = detect_corners(df, laps_analyzed=laps_analyzed, curvature_threshold_override=curvature_threshold_global)

    corners_meta = df.attrs.get("corners", {})
    corner_details = corners_meta.get("corner_details", [])
    logger.info(f"[DIAG] detect_corners retourné : {len(corner_details)} corners")
    logger.info(f"[{analysis_id}] Detected {len(corner_details)} corners")

    # Previously we filtered down to selected laps here. 
    # Now we keep the FULL session in df so that the frontend can overlay whichever laps it wants.
    pass

    df = calculate_optimal_trajectory(df)
    logger.info(f"[{analysis_id}] Step 5/5: Calculating score and coaching...")
    score_data = calculate_performance_score(df, corner_details, track_condition=track_condition)

    def sanitize_corner_data(corner_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            metrics = corner_data.get("metrics", {})
            entry_speed = metrics.get("entry_speed")
            exit_speed = metrics.get("exit_speed")
            corner_id = int(corner_data.get("corner_id", 0))
            out = {
                "corner_id": corner_id,
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
                "lap": corner_data.get("lap"),
                "per_lap_data": corner_data.get("per_lap_data", []),
                "label": f"V{corner_id}",
                "entry_index": corner_data.get("entry_index"),
                "apex_index": corner_data.get("apex_index"),
                "_entry_index_first_lap": corner_data.get("_entry_index_first_lap"),
                "_apex_index_first_lap": corner_data.get("_apex_index_first_lap"),
                "avg_cumulative_distance": corner_data.get("avg_cumulative_distance"),
            }
            if entry_speed is not None:
                out["entry_speed"] = float(entry_speed)
            if exit_speed is not None:
                out["exit_speed"] = float(exit_speed)
            if metrics.get("target_entry_speed") is not None:
                out["target_entry_speed"] = float(metrics["target_entry_speed"])
            if metrics.get("target_exit_speed") is not None:
                out["target_exit_speed"] = float(metrics["target_exit_speed"])
            return out
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
            analysis["apex_lat"] = analysis.get("apex_lat") if analysis.get("apex_lat") is not None else corner.get("apex_lat")
            analysis["apex_lon"] = analysis.get("apex_lon") if analysis.get("apex_lon") is not None else corner.get("apex_lon")
            analysis["per_lap_data"] = corner.get("per_lap_data", [])
            analysis["lap"] = corner.get("lap")
            analysis["entry_index"] = corner.get("entry_index")
            analysis["apex_index"] = corner.get("apex_index")
            analysis["_entry_index_first_lap"] = corner.get("_entry_index_first_lap", corner.get("entry_index"))
            analysis["_apex_index_first_lap"] = corner.get("_apex_index_first_lap", corner.get("apex_index"))
            analysis["avg_cumulative_distance"] = corner.get("avg_cumulative_distance")
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
                "entry_index": corner.get("entry_index"),
                "apex_index": corner.get("apex_index"),
                "_entry_index_first_lap": corner.get("_entry_index_first_lap", corner.get("entry_index")),
                "_apex_index_first_lap": corner.get("_apex_index_first_lap", corner.get("apex_index")),
                "avg_cumulative_distance": corner.get("avg_cumulative_distance"),
            })

    logger.info(f"[{analysis_id}] {len(corner_analysis_list)} corners analyzed successfully")

    # Virages uniques du circuit (dédupliquer par corner_id, conserver l'ordre de corner_details)
    # L'ordre correct est déjà établi par geometry.py via GPS curvilinear projection
    unique_by_id = {}
    for c in corner_analysis_list:
        cid = c.get("corner_id")
        if cid is not None and cid not in unique_by_id:
            unique_by_id[cid] = c
    unique_corner_analysis = list(unique_by_id.values())
    # Sort by corner_id — already set to the correct physical circuit order by geometry.py
    unique_corner_analysis.sort(key=lambda c: c.get("corner_id", float("inf")))
    logger.info(
        "[%s] [ordre] Corners in GPS-projected order: %s",
        analysis_id,
        [f"V{c.get('corner_id')} sort_idx={c.get('_sort_index', '?')}" for c in unique_corner_analysis],
    )
    logger.info(f"[{analysis_id}] [renumber] Renumbering {len(unique_corner_analysis)} unique corners...")
    final_id_to_new = {int(c.get("corner_id")): i for i, c in enumerate(unique_corner_analysis, start=1)}
    for i, c in enumerate(unique_corner_analysis, start=1):
        c["corner_id"] = i
        c["corner_number"] = i
        c["label"] = f"V{i}"
        c["avg_note"] = "Valeurs sur ce tour" if laps_analyzed == 1 else f"Valeurs moyennées sur {laps_analyzed} tours"

    if "corner_id" in df.columns:
        # Vectorized update for corner_id
        df["corner_id"] = df["corner_id"].map(lambda x: final_id_to_new.get(int(x), x) if pd.notna(x) else x)
    
    logger.info(f"[{analysis_id}] [renumber] Done. Filling apex coordinates...")
    # Remplir apex_lat/apex_lon depuis le df si manquants (pour que trajectoire + heatmap affichent tous les virages)
    lat_col = "latitude_smooth" if "latitude_smooth" in df.columns else "latitude"
    lon_col = "longitude_smooth" if "longitude_smooth" in df.columns else "longitude"
    for c in unique_corner_analysis:
        if (c.get("apex_lat") is None or c.get("apex_lon") is None) and c.get("apex_index") is not None:
            idx = c["apex_index"]
            if idx in df.index and lat_col in df.columns and lon_col in df.columns:
                c["apex_lat"] = float(df.at[idx, lat_col]) if pd.notna(df.at[idx, lat_col]) else c.get("apex_lat")
                c["apex_lon"] = float(df.at[idx, lon_col]) if pd.notna(df.at[idx, lon_col]) else c.get("apex_lon")
    corners_detected = len(unique_corner_analysis)

    # Une seule source de vérité : overall_score = sum(breakdown) depuis calculate_performance_score
    validate_score_consistency(score_data)

    logger.info(f"[{analysis_id}] Generating coaching advice...")
    try:
        coaching_advice_list = generate_coaching_advice(
            df, corner_details, score_data, unique_corner_analysis,
            track_condition=track_condition,
            track_temperature=track_temperature,
            laps_analyzed=laps_analyzed,
        )
    except Exception as e:
        logger.warning(f"[{analysis_id}] Failed to generate coaching advice: {e}")
        coaching_advice_list = []

    logger.info(f"[{analysis_id}] Generating plots (PNG)...")
    df.attrs["corner_analysis"] = unique_corner_analysis
    df.attrs["score_data"] = score_data
    df.attrs["overall_score"] = score_data.get("overall_score", 0.0)
    plots_urls = generate_all_plots_base64(df)
    
    logger.info(f"[{analysis_id}] Generating plot data (JSON)...")
    plot_data = generate_plot_data(df)
    
    # Dupliquer le speed trace en variante zoomée si disponible
    try:
        speed_trace_url = plots_urls.get("speed_trace")
        if speed_trace_url:
            plots_urls.setdefault("speed_trace_zoomed", speed_trace_url)
    except Exception:
        pass

    logger.info(f"[{analysis_id}] Finalizing response...")
    processing_time = (datetime.now() - start_time).total_seconds()

    # Log des graphiques réellement générés (non nuls) pour debug
    try:
        non_null_plots = [k for k, v in plots_urls.items() if v]
        logger.info(f"[{analysis_id}] Plots générés (non nuls): {non_null_plots}")
    except Exception as e:
        logger.warning(f"[{analysis_id}] Impossible de logger les plots générés: {e}")

    processing_time = (datetime.now() - start_time).total_seconds()

    # Calculate Session Statistics
    best_lap_time: Optional[float] = None
    lap_times: Optional[List[float]] = None
    fastest_lap_number: Optional[int] = None
    max_speed: Optional[float] = None
    max_speed_lap: Optional[int] = None
    consistency_gap: Optional[float] = None
    improvement_gap: Optional[float] = None

    # Calculate lap times (excluding lap 0 outliers if possible)
    valid_laps_dict = {}
    if "lap_number" in df.columns and "time" in df.columns:
        for lap in sorted(df["lap_number"].dropna().unique().astype(int).tolist()):
            grp = df[df["lap_number"] == lap]["time"].dropna()
            if len(grp) >= 2:
                valid_laps_dict[lap] = round(float(grp.max() - grp.min()), 3)
    
    if valid_laps_dict:
        # Ignore lap 0 if it exists
        if len(valid_laps_dict) > 1 and 0 in valid_laps_dict:
            del valid_laps_dict[0]
            
        lap_times = list(valid_laps_dict.values())
        best_lap_time = min(lap_times)
        
        # Find fastest lap number
        for L, t in valid_laps_dict.items():
            if t == best_lap_time:
                fastest_lap_number = L
                break
                
        # Calculate stats
        if len(lap_times) >= 2:
            import statistics
            worst_lap_time = max(lap_times)
            improvement_gap = round(worst_lap_time - best_lap_time, 3)
            # Consistency can be standard deviation (or average gap). We map it to std dev of lap times.
            try:
                consistency_gap = round(statistics.stdev(lap_times), 3)
            except Exception:
                consistency_gap = 0.0
        else:
            improvement_gap = 0.0
            consistency_gap = 0.0
    else:
        lap_time = 0.0
        best_lap_time = 0.0
        lap_times = []
        
    lap_time = best_lap_time or 0.0

    # Calculate Max Speed & Lap
    if "speed_kmh" in df.columns and "lap_number" in df.columns:
        valid_speed_df = df[df["lap_number"] > 0] if 0 in df["lap_number"].unique() else df
        if len(valid_speed_df) > 0:
            max_row = valid_speed_df.loc[valid_speed_df["speed_kmh"].idxmax()]
            max_speed = round(float(max_row["speed_kmh"]), 1)
            max_speed_lap = int(max_row["lap_number"])
        else:
            max_speed = round(float(df["speed_kmh"].max()), 1)
            max_speed_lap = int(df.loc[df["speed_kmh"].idxmax()]["lap_number"])
    elif "speed_kmh" in df.columns:
        max_speed = round(float(df["speed_kmh"].max()), 1)
        
    logger.info(f"[{analysis_id}] Session Stats: Best={best_lap_time}s (L{fastest_lap_number}), Max Speed={max_speed}km/h (L{max_speed_lap}), Cons={consistency_gap}s, Imp={improvement_gap}s")

    logger.info(f"[{analysis_id}] ✅ Completed in {processing_time:.2f}s")

    response = AnalysisResponse(
        success=True,
        analysis_id=analysis_id,
        timestamp=datetime.now(),
        corners_detected=corners_detected,
        lap_time=lap_time,
        best_lap_time=best_lap_time,
        lap_times=lap_times,
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
        plot_data=plot_data,
        statistics=Statistics(
            processing_time_seconds=processing_time,
            data_points=int(len(df)),
            best_corners=score_data.get("details", {}).get("best_corners", [])[:3],
            worst_corners=score_data.get("details", {}).get("worst_corners", [])[:3],
            avg_apex_distance=float(score_data.get("details", {}).get("avg_apex_distance", 0.0)),
            avg_apex_speed_efficiency=float(score_data.get("details", {}).get("avg_apex_speed_efficiency", 0.0)),
            laps_analyzed=laps_analyzed,
            fastest_lap_number=fastest_lap_number,
            max_speed=max_speed,
            max_speed_lap=max_speed_lap,
            consistency_gap=consistency_gap,
            improvement_gap=improvement_gap,
        ),
        session_conditions=SessionConditions(
            session_name=session_name,
            track_condition=track_condition,
            track_temperature=track_temperature,
        ),
    )
    return response.dict(exclude_none=True)


class AnalysisService:
    """Service d'analyse de télémétrie"""
    
    def __init__(self, lap_filter: Optional[List[int]] = None):
        """Initialiser le service"""
        os.makedirs(settings.TEMP_DIR, exist_ok=True)
        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        self._lap_filter = lap_filter if lap_filter else None
    
    async def parse_laps(self, file: UploadFile) -> List[Dict[str, Any]]:
        """
        Parse le fichier CSV et retourne la liste des tours détectés
        (lap_number, lap_time_seconds, points_count, is_outlier).
        Réutilise la même logique que le pipeline (load, savgol, geometry, detect_laps).
        """
        temp_path = None
        try:
            temp_path = os.path.join(settings.TEMP_DIR, f"parse_laps_{uuid.uuid4().hex[:8]}_{file.filename}")
            content = await file.read()
            if len(content) > 50 * 1024 * 1024:
                raise ValueError("Fichier trop volumineux (max 50 MB).")
            with open(temp_path, "wb") as f:
                f.write(content)
            await file.seek(0)

            beacon_markers = []
            try:
                with open(temp_path, "r", encoding="utf-8", errors="ignore") as bfile:
                    for i, bline in enumerate(bfile):
                        if i > 20:
                            break
                        if "Beacon" in bline or "beacon" in bline:
                            parts = bline.strip().replace('"', "").split(",")
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
            except Exception:
                pass

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                _parse_laps_sync,
                temp_path,
                beacon_markers,
            )
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
    
    async def process_telemetry(
        self,
        file: UploadFile,
        analysis_id: str,
        track_condition: str = "dry",
        track_temperature: Optional[float] = None,
        session_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Traiter un fichier de télémétrie complet.
        
        Args:
            file: Fichier CSV uploadé
            analysis_id: ID unique de l'analyse
            track_condition: dry | damp | wet | rain
            track_temperature: Température piste °C (optionnel)
        
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
            lap_filter = getattr(self, "_lap_filter", None)
            result = await loop.run_in_executor(
                None,
                _run_analysis_pipeline_sync,
                temp_path,
                beacon_markers,
                analysis_id,
                start_time,
                lap_filter,
                track_condition,
                track_temperature,
                session_name,
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
