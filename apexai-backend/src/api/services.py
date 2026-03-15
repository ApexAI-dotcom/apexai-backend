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
from src.visualization.visualization import generate_all_plots_base64

from .config import settings
from .models import (
    AnalysisResponse, PerformanceScore, ScoreBreakdown,
    CornerAnalysis, CoachingAdvice, PlotUrls, Statistics, SessionConditions
)

logger = logging.getLogger(__name__)

BUFFER_BEFORE_AFTER = 75
BUFFER_BETWEEN_GROUPS = 50


def _build_plot_data(
    df: "pd.DataFrame",
    corner_analysis: List[Dict[str, Any]],
    score_data: Dict[str, Any],
    lap_time_by_lap: Optional[Dict[int, float]] = None,
) -> Dict[str, Any]:
    """Données brutes pour recréer les graphiques côté frontend (Recharts)."""
    out = {}
    # --- speed_trace : laps avec lap_time, is_reference ; secteurs sur 1 tour ; avg_speed_kmh arrondi ---
    try:
        if "cumulative_distance" in df.columns and "speed" in df.columns:
            dist = pd.to_numeric(df["cumulative_distance"], errors="coerce").values
            speed = pd.to_numeric(df["speed"], errors="coerce").values
            d_min = np.nanmin(dist)
            dist_rel = np.where(np.isnan(dist), np.nan, dist - d_min)
            total_distance = float(np.nanmax(dist_rel)) if np.any(np.isfinite(dist_rel)) else 0.0
            laps_list = []
            lap_distances: List[float] = []
            lap_numbers_sorted: List[int] = []
            if "lap_number" in df.columns:
                for i, lap_num in enumerate(sorted(df["lap_number"].dropna().unique())):
                    if lap_num < 1:
                        continue
                    mask = df["lap_number"].values == lap_num
                    if not mask.any():
                        continue
                    d = dist_rel[mask]
                    s = speed[mask]
                    d_clean = d[~np.isnan(d)]
                    lap_len = float(np.nanmax(d_clean) - np.nanmin(d_clean)) if len(d_clean) else 0.0
                    lap_distances.append(lap_len)
                    lap_numbers_sorted.append(int(lap_num))
                    lap_time = None
                    if lap_time_by_lap is not None:
                        lap_time = round(lap_time_by_lap.get(int(lap_num)), 3) if lap_time_by_lap.get(int(lap_num)) is not None else None
                    best_lap_num = min(lap_time_by_lap, key=lap_time_by_lap.get) if lap_time_by_lap else None
                    is_ref = best_lap_num is not None and int(lap_num) == int(best_lap_num)
                    laps_list.append({
                        "lap_number": int(lap_num),
                        "lap_time": lap_time,
                        "distance_m": [round(x, 1) for x in d_clean.tolist()[:500]],
                        "speed_kmh": [round(float(x), 1) for x in s[~np.isnan(s)].tolist()[:500]],
                        "is_reference": is_ref,
                    })
            if not laps_list:
                laps_list = [{
                    "lap_number": 1,
                    "lap_time": round(lap_time_by_lap.get(1), 3) if lap_time_by_lap and lap_time_by_lap.get(1) is not None else None,
                    "distance_m": [round(x, 1) for x in (dist_rel[~np.isnan(dist_rel)].tolist()[:500])],
                    "speed_kmh": [round(float(x), 1) for x in speed[~np.isnan(speed)].tolist()[:500]],
                    "is_reference": True,
                }]
                lap_distances = [total_distance]
            track_length_one_lap = lap_distances[0] if lap_distances else (total_distance / max(1, len(laps_list)))
            sectors = [
                {"name": "S1", "start_m": round(0, 1), "end_m": round(track_length_one_lap / 3.0, 1)},
                {"name": "S2", "start_m": round(track_length_one_lap / 3.0, 1), "end_m": round(2.0 * track_length_one_lap / 3.0, 1)},
                {"name": "S3", "start_m": round(2.0 * track_length_one_lap / 3.0, 1), "end_m": round(track_length_one_lap, 1)},
            ]
            if np.any(np.isfinite(speed)):
                raw_mean = float(np.nanmean(speed))
                avg_speed = round(raw_mean * 3.6, 1) if raw_mean < 100 else round(raw_mean, 1)
            else:
                avg_speed = 0.0
            out["speed_trace"] = {
                "laps": laps_list,
                "sectors": sectors,
                "avg_speed_kmh": avg_speed,
            }
    except Exception as e:
        logger.warning("_build_plot_data speed_trace: %s", e, exc_info=False)
    # --- trajectory_2d : corners avec grade, corner_type, apex_speed ---
    try:
        if "latitude" in df.columns and "longitude" in df.columns:
            lat_col = "latitude_smooth" if "latitude_smooth" in df.columns else "latitude"
            lon_col = "longitude_smooth" if "longitude_smooth" in df.columns else "longitude"
            laps_list = []
            if "lap_number" in df.columns:
                for lap_num in sorted(df["lap_number"].dropna().unique()):
                    if lap_num >= 1:
                        mask = df["lap_number"].values == lap_num
                        laps_list.append({
                            "lap_number": int(lap_num),
                            "lat": [round(float(x), 6) for x in df.loc[mask, lat_col].dropna().tolist()[:300]],
                            "lon": [round(float(x), 6) for x in df.loc[mask, lon_col].dropna().tolist()[:300]],
                            "speed_kmh": [round(float(x), 1) for x in (df.loc[mask, "speed"].dropna().tolist()[:300] if "speed" in df.columns else [])],
                        })
            corners_list = [
                {
                    "id": c.get("corner_number", c.get("corner_id")),
                    "lat": round(float(c.get("apex_lat") or 0), 6),
                    "lon": round(float(c.get("apex_lon") or 0), 6),
                    "label": c.get("label", f"Virage {c.get('corner_number', c.get('corner_id', 0))}"),
                    "grade": c.get("grade", "C"),
                    "corner_type": c.get("corner_type", "right"),
                    "apex_speed": round(float(c.get("apex_speed_real") or 0), 1),
                }
                for c in corner_analysis[:15]
            ]
            out["trajectory_2d"] = {"laps": laps_list or [], "corners": corners_list}
    except Exception as e:
        logger.warning("_build_plot_data trajectory_2d: %s", e, exc_info=False)
    # --- performance_radar (déjà arrondi via float) ---
    try:
        bd = score_data.get("breakdown", {})
        out["performance_radar"] = {
            "axes": ["Précision Apex", "Régularité", "Vitesse Apex", "Secteurs"],
            "values": [round(float(bd.get("apex_precision", 0)), 1), round(float(bd.get("trajectory_consistency", 0)), 1), round(float(bd.get("apex_speed", 0)), 1), round(float(bd.get("sector_times", 0)), 1)],
            "max_values": [30, 25, 25, 20],
        }
    except Exception as e:
        logger.warning("_build_plot_data performance_radar: %s", e, exc_info=False)
    # --- apex_margin : corners enrichis (corner_type, grade, score, apex_speed_real/optimal, time_lost, entry/exit_speed) ---
    try:
        apex_list = []
        for c in corner_analysis[:15]:
            real = float(c.get("apex_speed_real") or 0)
            opt = float(c.get("apex_speed_optimal") or real)
            margin = round(opt - real, 1) if opt >= real else 0.0
            status = "optimal" if margin <= 0.5 else ("good" if margin <= 3 else "warning")
            apex_list.append({
                "label": c.get("label", f"Virage {c.get('corner_number', c.get('corner_id', 0))}"),
                "margin_kmh": margin,
                "status": status,
                "corner_type": c.get("corner_type", "right"),
                "grade": c.get("grade", "C"),
                "score": round(float(c.get("score", 0)), 1),
                "apex_speed_real": round(real, 1),
                "apex_speed_optimal": round(opt, 1),
                "time_lost": round(float(c.get("time_lost") or 0), 3),
                "entry_speed": round(float(c.get("entry_speed") or c.get("entry_speed_kmh") or 0), 1),
                "exit_speed": round(float(c.get("exit_speed") or c.get("exit_speed_kmh") or 0), 1),
            })
        out["apex_margin"] = {"corners": apex_list}
    except Exception as e:
        logger.warning("_build_plot_data apex_margin: %s", e, exc_info=False)
    # --- throttle_brake (si throttle/brake ou AccelerometerX) ---
    try:
        has_throttle_brake = "throttle" in df.columns and "brake" in df.columns
        if not has_throttle_brake and "AccelerometerX" in df.columns:
            has_throttle_brake = True
        if has_throttle_brake and "cumulative_distance" in df.columns:
            dist_col = pd.to_numeric(df["cumulative_distance"], errors="coerce").values
            if "throttle" in df.columns and "brake" in df.columns:
                throttle_vals = pd.to_numeric(df["throttle"], errors="coerce").fillna(0).values
                brake_vals = pd.to_numeric(df["brake"], errors="coerce").fillna(0).values
            else:
                ax = pd.to_numeric(df["AccelerometerX"], errors="coerce").fillna(0).values
                throttle_vals = np.clip(ax * 50 + 50, 0, 100) if np.nanmin(ax) < 0 else np.clip(ax, 0, 100)
                brake_vals = np.clip(-ax * 50 + 50, 0, 100) if np.nanmin(ax) < 0 else np.zeros_like(ax)
            tb_laps = []
            if "lap_number" in df.columns:
                for lap_num in sorted(df["lap_number"].dropna().unique()):
                    if lap_num < 1:
                        continue
                    mask = df["lap_number"].values == lap_num
                    d = dist_col[mask]
                    t = throttle_vals[mask]
                    b = brake_vals[mask]
                    tb_laps.append({
                        "lap_number": int(lap_num),
                        "distance_m": [round(float(x), 1) for x in d[~np.isnan(d)].tolist()[:500]],
                        "throttle_pct": [round(float(x), 1) for x in t.tolist()[:500]],
                        "brake_pct": [round(float(x), 1) for x in b.tolist()[:500]],
                    })
            if tb_laps:
                out["throttle_brake"] = {"laps": tb_laps}
    except Exception as e:
        logger.warning("_build_plot_data throttle_brake: %s", e, exc_info=False)
    # --- time_delta : reference (meilleur) vs comparison (2e) ---
    try:
        if lap_time_by_lap and len(lap_time_by_lap) >= 2 and "time" in df.columns and "cumulative_distance" in df.columns and "lap_number" in df.columns:
            sorted_laps = sorted(lap_time_by_lap.items(), key=lambda x: x[1])
            ref_lap_num = sorted_laps[0][0]
            comp_lap_num = sorted_laps[1][0]
            ref_mask = df["lap_number"].values == ref_lap_num
            comp_mask = df["lap_number"].values == comp_lap_num
            if ref_mask.any() and comp_mask.any():
                dist_ref = pd.to_numeric(df.loc[ref_mask, "cumulative_distance"], errors="coerce").values
                time_ref = pd.to_numeric(df.loc[ref_mask, "time"], errors="coerce").values
                dist_comp = pd.to_numeric(df.loc[comp_mask, "cumulative_distance"], errors="coerce").values
                time_comp = pd.to_numeric(df.loc[comp_mask, "time"], errors="coerce").values
                d_min_ref, d_max_ref = np.nanmin(dist_ref), np.nanmax(dist_ref)
                d_min_comp, d_max_comp = np.nanmin(dist_comp), np.nanmax(dist_comp)
                track_len = min(d_max_ref - d_min_ref, d_max_comp - d_min_comp)
                if track_len <= 0:
                    raise ValueError("track_len <= 0")
                dist_ref_rel = (dist_ref - d_min_ref)[~np.isnan(dist_ref) & ~np.isnan(time_ref)]
                time_ref_clean = time_ref[~np.isnan(dist_ref) & ~np.isnan(time_ref)]
                dist_comp_rel = (dist_comp - d_min_comp)[~np.isnan(dist_comp) & ~np.isnan(time_comp)]
                time_comp_clean = time_comp[~np.isnan(dist_comp) & ~np.isnan(time_comp)]
                if len(dist_ref_rel) < 2 or len(dist_comp_rel) < 2:
                    raise ValueError("not enough points")
                order_ref = np.argsort(dist_ref_rel)
                order_comp = np.argsort(dist_comp_rel)
                dist_ref_rel = dist_ref_rel[order_ref]
                time_ref_clean = time_ref_clean[order_ref]
                dist_comp_rel = dist_comp_rel[order_comp]
                time_comp_clean = time_comp_clean[order_comp]
                n_pts = min(100, len(dist_ref_rel), len(dist_comp_rel))
                distance_m = np.linspace(0, track_len, n_pts)
                t_ref_interp = np.interp(distance_m, dist_ref_rel, time_ref_clean)
                t_comp_interp = np.interp(distance_m, dist_comp_rel, time_comp_clean)
                delta_s = [round(float(t_comp_interp[i] - t_ref_interp[i]), 3) for i in range(len(distance_m))]
                distance_m = [round(float(x), 1) for x in distance_m.tolist()]
                out["time_delta"] = {
                    "reference_lap": int(ref_lap_num),
                    "comparison_lap": int(comp_lap_num),
                    "distance_m": distance_m,
                    "delta_s": delta_s,
                }
    except Exception as e:
        logger.warning("_build_plot_data time_delta: %s", e, exc_info=False)
    return out


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
        threshold = 1.5 * median_time
        for lap in laps_out:
            if lap["lap_number"] == 0:
                lap["is_outlier"] = True
            elif lap["lap_time_seconds"] > threshold:
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
    debug: bool = False,
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

    # Si beacons présents et pas de lap_filter : sélectionner les 3 meilleurs tours (non-outlier)
    if lap_filter is None and beacon_markers and len(beacon_markers) >= 2:
        lap_times_s = [beacon_markers[i + 1] - beacon_markers[i] for i in range(len(beacon_markers) - 1)]
        if lap_times_s:
            median_t = float(np.median(lap_times_s))
            threshold_t = 1.5 * median_t
            fast_laps = [(i + 1, t) for i, t in enumerate(lap_times_s) if t <= threshold_t]
            fast_laps.sort(key=lambda x: x[1])
            lap_filter = [lap_num for lap_num, _ in fast_laps[:3]]
            if lap_filter:
                logger.info(f"[{analysis_id}] Auto-selected 3 best laps from beacons: {lap_filter}")

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
    laps_available_full = []
    if "lap_number" in df.columns:
        laps_available_full = sorted(df["lap_number"].dropna().unique().astype(int).tolist())
        logger.info(f"[DIAG] Tours disponibles (lap_number): {laps_available_full}")
    if lap_filter:
        logger.info(f"[DIAG] Tours sélectionnés : {lap_filter}")
        laps_analyzed = len(lap_filter)
        n_before = len(df)
        df = _filter_laps_with_buffer(df, lap_filter, analysis_id)
        logger.info(f"[DIAG] Rows après filtrage : {len(df)} (was {n_before}, full track)")
        logger.info(f"[{analysis_id}] Filtered to laps {lap_filter} with buffer: {len(df)} rows (was {n_before})")
        if len(df) < 10:
            raise ValueError("Pas assez de points après filtrage par tours (min. 10).")
    else:
        if "lap_number" in df.columns:
            laps_analyzed = int(df["lap_number"].nunique())
    logger.info(f"[DIAG] Appel detect_corners avec {len(df)} rows, laps_analyzed={laps_analyzed}")
    logger.info(f"[{analysis_id}] Step 4/5: Detecting corners...")
    df = detect_corners(df, laps_analyzed=laps_analyzed, curvature_threshold_override=curvature_threshold_global)

    corners_meta = df.attrs.get("corners", {})
    corner_details = corners_meta.get("corner_details", [])
    logger.info(f"[DIAG] detect_corners retourné : {len(corner_details)} corners")
    logger.info(f"[{analysis_id}] Detected {len(corner_details)} corners")

    # Refiltrer aux tours sélectionnés uniquement pour les calculs de performance (exclure buffer)
    if lap_filter and "lap_number" in df.columns:
        df_perf = df[df["lap_number"].isin(lap_filter)].copy()
        valid_idx = set(df_perf.index)
        lap_set = set(lap_filter)
        kept_corners = []
        for c in corner_details:
            ei, ai, exi = c.get("entry_index"), c.get("apex_index"), c.get("exit_index")
            per_lap = c.get("per_lap_data") or []
            chosen = None
            if per_lap:
                for pl in per_lap:
                    if pl.get("lap") in lap_set:
                        e, a, ex = pl.get("entry_index"), pl.get("apex_index"), pl.get("exit_index")
                        if e is not None and a is not None and ex is not None and e in valid_idx and a in valid_idx and ex in valid_idx:
                            chosen = (e, a, ex)
                            break
            if chosen is None and ei in valid_idx and ai in valid_idx and exi in valid_idx:
                chosen = (ei, ai, exi)
            if chosen is not None:
                c["entry_index"], c["apex_index"], c["exit_index"] = chosen
                # Garder seulement per_lap_data des tours sélectionnés
                c["per_lap_data"] = [pl for pl in per_lap if pl.get("lap") in lap_set]
                kept_corners.append(c)
        corner_details = kept_corners
        # Renuméroter V1..Vn après suppression d’un virage (ordre conservé)
        refilter_id_to_new = {}
        for i, c in enumerate(corner_details, start=1):
            old_id = c.get("id")
            refilter_id_to_new[old_id] = i
            c["id"] = i
            c["corner_id"] = i
            c["corner_number"] = i
            c["label"] = f"V{i}"
        df = df_perf.reset_index(drop=True)
        for idx in df.index:
            if df.at[idx, "is_corner"]:
                old_cid = df.at[idx, "corner_id"]
                df.at[idx, "corner_id"] = refilter_id_to_new.get(old_cid, old_cid)
        old_to_new = {old: i for i, old in enumerate(df_perf.index)}
        for c in corner_details:
            c["entry_index"] = old_to_new.get(c["entry_index"], c["entry_index"])
            c["apex_index"] = old_to_new.get(c["apex_index"], c["apex_index"])
            c["exit_index"] = old_to_new.get(c["exit_index"], c["exit_index"])
            for pl in c.get("per_lap_data") or []:
                for key in ("entry_index", "apex_index", "exit_index"):
                    if key in pl and pl[key] is not None:
                        pl[key] = old_to_new.get(pl[key], pl[key])
        corners_meta["corner_details"] = corner_details
        df.attrs["corners"] = corners_meta
        logger.info(f"[{analysis_id}] Refiltered to selected laps only: {len(df)} rows, {len(corner_details)} corners")
        # Corner order is already correct from geometry.py GPS projection — no re-sorting needed

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
    # Forcer renumérotation séquentielle V1..Vn (ordre liste = ordre circuit) pour affichage cohérent
    final_id_to_new = {}
    for i, c in enumerate(unique_corner_analysis, start=1):
        old_id = c.get("corner_id")
        final_id_to_new[old_id] = i
        c["corner_id"] = i
        c["corner_number"] = i
        c["label"] = f"V{i}"
    for idx in df.index:
        if df.at[idx, "is_corner"]:
            old_cid = df.at[idx, "corner_id"]
            df.at[idx, "corner_id"] = final_id_to_new.get(old_cid, old_cid)
    for c in unique_corner_analysis:
        c["avg_note"] = "Valeurs sur ce tour" if laps_analyzed == 1 else f"Valeurs moyennées sur {laps_analyzed} tours"
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

    logger.info(f"[{analysis_id}] Generating plots...")
    df.attrs["corner_analysis"] = unique_corner_analysis
    df.attrs["score_data"] = score_data
    df.attrs["overall_score"] = score_data.get("overall_score", 0.0)
    plots_urls = generate_all_plots_base64(df)

    processing_time = (datetime.now() - start_time).total_seconds()

    # Temps par tour : filtrés aux tours sélectionnés (lap_filter)
    best_lap_time: Optional[float] = None
    lap_times: Optional[List[float]] = None
    if beacon_markers and len(beacon_markers) >= 2:
        # lap_times[k] = durée du tour k+1 (beacon_markers[k] = timestamp fin du tour k+1)
        timed_laps = []
        for i in range(1, len(beacon_markers)):
            timed_laps.append(beacon_markers[i] - beacon_markers[i - 1])
        all_lap_times = [round(t, 3) for t in timed_laps]
        if lap_filter:
            lap_times = [all_lap_times[i - 1] for i in lap_filter if 1 <= i <= len(all_lap_times)]
        else:
            lap_times = all_lap_times
        best_lap_time = round(min(lap_times), 3) if lap_times else None
        lap_time = best_lap_time or 0.0
        logger.info(f"[{analysis_id}] Meilleur tour: {best_lap_time}s sur {len(lap_times)} tour(s)")
    else:
        if lap_filter and "time" in df.columns and "lap_number" in df.columns:
            lap_times = []
            for lap in sorted(lap_filter):
                grp = df[df["lap_number"] == lap]["time"].dropna()
                if len(grp) >= 2:
                    lap_times.append(round(float(grp.max() - grp.min()), 3))
            best_lap_time = round(min(lap_times), 3) if lap_times else None
            lap_time = best_lap_time or 0.0
        else:
            if "time" in df.columns and len(df) > 0:
                time_values = df["time"].dropna()
                lap_time = round(float(time_values.iloc[-1] - time_values.iloc[0]), 3) if len(time_values) > 0 else 0.0
            else:
                lap_time = 0.0
            lap_times = [lap_time]
            best_lap_time = lap_time

    logger.info(f"[{analysis_id}] ✅ Completed in {processing_time:.2f}s")

    # Mapping lap_number -> lap_time pour plot_data (speed_trace lap_time, is_reference, time_delta)
    if lap_times:
        if lap_filter and len(lap_filter) == len(lap_times):
            _lap_time_by_lap = dict(zip(lap_filter, lap_times))
        elif "lap_number" in df.columns:
            _lap_nums = sorted(df["lap_number"].dropna().unique().astype(int).tolist())
            _lap_time_by_lap = dict(zip(_lap_nums, lap_times)) if len(_lap_nums) == len(lap_times) else None
        else:
            _lap_time_by_lap = dict(zip(range(1, len(lap_times) + 1), lap_times))
    else:
        _lap_time_by_lap = None

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
        statistics=Statistics(
            processing_time_seconds=processing_time,
            data_points=int(len(df)),
            best_corners=score_data.get("details", {}).get("best_corners", [])[:3],
            worst_corners=score_data.get("details", {}).get("worst_corners", [])[:3],
            avg_apex_distance=float(score_data.get("details", {}).get("avg_apex_distance", 0.0)),
            avg_apex_speed_efficiency=float(score_data.get("details", {}).get("avg_apex_speed_efficiency", 0.0)),
            laps_analyzed=laps_analyzed,
        ),
        session_conditions=SessionConditions(
            track_condition=track_condition,
            track_temperature=track_temperature,
        ),
        plot_data=_build_plot_data(df, unique_corner_analysis, score_data, lap_time_by_lap=_lap_time_by_lap),
    )
    result = response.model_dump(mode="python", exclude_none=True)
    if debug:
        result["debug_laps"] = laps_available_full
        result["debug_beacons"] = len(beacon_markers) if beacon_markers else 0
        result["debug_breakdown"] = score_data.get("breakdown")
    return result


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
        debug: bool = False,
    ) -> Dict[str, Any]:
        """
        Traiter un fichier de télémétrie complet.
        
        Args:
            file: Fichier CSV uploadé
            analysis_id: ID unique de l'analyse
            track_condition: dry | damp | wet | rain
            track_temperature: Température piste °C (optionnel)
            debug: Si True, ajoute debug_laps, debug_beacons, debug_breakdown à la réponse
        
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
                debug,
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
