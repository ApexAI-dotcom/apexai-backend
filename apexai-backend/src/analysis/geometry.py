#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Geometry Analysis (Karting Pro)
Calcul de géométrie trajectoire et détection apex avec précision F1-level
"""

import pandas as pd
import numpy as np
from scipy.signal import savgol_filter
from scipy.ndimage import label
from typing import Dict, Any, List, Tuple, Optional
import warnings
import math
import statistics

# CONSTANTES
EARTH_RADIUS_M = 6371000  # Rayon de la Terre en mètres
GRAVITY_MS2 = 9.81  # Accélération gravitationnelle en m/s²
FRICTION_COEFF = 1.1  # Coefficient de friction karting slick sec
MIN_CORNER_LATERAL_G = 0.08  # Seuil minimum d'accélération latérale pour détection virage
MIN_CORNER_DURATION_S = 0.3  # Durée minimum d'un virage en secondes
MIN_CORNER_DISTANCE_M = 5.0  # Distance minimum d'un virage en mètres


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule la distance en mètres entre deux points GPS (formule de Haversine).
    
    Args:
        lat1: Latitude du premier point (degrés)
        lon1: Longitude du premier point (degrés)
        lat2: Latitude du second point (degrés)
        lon2: Longitude du second point (degrés)
    
    Returns:
        Distance en mètres entre les deux points
    """
    try:
        phi1 = np.radians(lat1)
        phi2 = np.radians(lat2)
        delta_phi = np.radians(lat2 - lat1)
        delta_lambda = np.radians(lon2 - lon1)
        
        a = np.sin(delta_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        
        return EARTH_RADIUS_M * c
    except (ValueError, TypeError):
        return 0.0


def _get_apex_gps(df_work: pd.DataFrame, indices: List[int]) -> Tuple[Optional[float], Optional[float]]:
    """
    Retourne (lat, lon) du point d'apex (vitesse min) parmi les indices du segment.
    Gère les lat/lon manquantes ou hors bounds pour éviter virages absents (ex. V2).
    """
    if not indices or len(df_work) == 0:
        return None, None
    lat_col = 'latitude_smooth' if 'latitude_smooth' in df_work.columns else 'latitude'
    lon_col = 'longitude_smooth' if 'longitude_smooth' in df_work.columns else 'longitude'
    if lat_col not in df_work.columns or lon_col not in df_work.columns:
        return None, None
    try:
        valid_indices = [
            i for i in indices
            if 0 <= i < len(df_work)
            and pd.notna(df_work.iloc[i][lat_col])
            and pd.notna(df_work.iloc[i][lon_col])
        ]
        if not valid_indices:
            return None, None
        speed_col = 'speed' if 'speed' in df_work.columns else 'GPS Speed'
        if speed_col in df_work.columns:
            speeds = df_work.iloc[valid_indices][speed_col]
            apex_rel = speeds.values.argmin()
            apex_iloc = valid_indices[apex_rel]
        else:
            apex_iloc = valid_indices[len(valid_indices) // 2]
        lat = float(df_work.iloc[apex_iloc][lat_col])
        lon = float(df_work.iloc[apex_iloc][lon_col])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None, None
        if lat == 0.0 and lon == 0.0:
            return None, None
        return lat, lon
    except Exception as e:
        warnings.warn(f"Erreur calcul apex GPS: {e}")
        return None, None


def _smooth_heading(heading: np.ndarray, window: int = 5) -> np.ndarray:
    """
    Lisse le cap (heading) en gérant les discontinuités 359° → 0°.
    
    Utilise np.unwrap pour convertir en valeurs continues,
    puis applique un filtre médian pour le lissage.
    
    Args:
        heading: Array de caps en degrés [0, 360]
        window: Taille de la fenêtre du filtre (doit être impair)
    
    Returns:
        Array de caps lissés en degrés [0, 360]
    """
    if len(heading) == 0:
        return heading
    
    try:
        # Convertir en radians pour unwrap
        heading_rad = np.deg2rad(heading)
        
        # Unwrap pour gérer les discontinuités 359° → 0°
        heading_unwrapped = np.unwrap(heading_rad)
        
        # Rolling median pour stabiliser (approximation manuelle)
        if len(heading_unwrapped) >= window:
            # Assurer que window est impair
            if window % 2 == 0:
                window = window - 1
            
            heading_smooth_rad = np.zeros_like(heading_unwrapped)
            half_window = window // 2
            
            for i in range(len(heading_unwrapped)):
                start = max(0, i - half_window)
                end = min(len(heading_unwrapped), i + half_window + 1)
                heading_smooth_rad[i] = np.median(heading_unwrapped[start:end])
        else:
            heading_smooth_rad = heading_unwrapped
        
        # Reconvertir en degrés et wrap dans [0, 360]
        heading_smooth_deg = np.rad2deg(heading_smooth_rad)
        heading_smooth_deg = heading_smooth_deg % 360
        
        return heading_smooth_deg
    except Exception:
        return heading


def calculate_trajectory_geometry(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule la géométrie de trajectoire avec précision F1-level.
    
    Calcule heading, courbure, accélération latérale, distances, et infère throttle/brake.
    
    Args:
        df: DataFrame avec colonnes 'latitude_smooth', 'longitude_smooth', 'speed', 'time'
    
    Returns:
        DataFrame enrichi avec colonnes :
        - 'heading' : cap en degrés [0, 360]
        - 'curvature' : courbure en 1/m (+ = gauche, - = droite)
        - 'lateral_g' : accélération latérale en g (clampé -3g à +3g)
        - 'segment_distance' : distance depuis point précédent (m)
        - 'cumulative_distance' : distance cumulée (m)
        - 'throttle' : estimation throttle 0-100% (si absent)
        - 'brake' : estimation brake 0-100% (si absent)
    
    Raises:
        ValueError: Si colonnes requises manquantes
    """
    # Validation colonnes requises
    required_cols = ['latitude_smooth', 'longitude_smooth', 'speed', 'time']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        raise ValueError(f"❌ Colonnes manquantes : {', '.join(missing_cols)}")
    
    df_result = df.copy()
    n_points = len(df_result)
    
    if n_points < 3:
        raise ValueError(f"❌ DataFrame trop petit : {n_points} lignes (minimum 3 requis)")
    
    # Convertir en numérique
    try:
        lat = pd.to_numeric(df_result['latitude_smooth'], errors='coerce').values
        lon = pd.to_numeric(df_result['longitude_smooth'], errors='coerce').values
        speed = pd.to_numeric(df_result['speed'], errors='coerce').values
        time = pd.to_numeric(df_result['time'], errors='coerce').values
    except Exception as e:
        raise ValueError(f"❌ Erreur conversion numérique : {str(e)}")
    
    # Vérifier NaN
    nan_ratio = np.sum(np.isnan(lat) | np.isnan(lon) | np.isnan(speed)) / n_points
    if nan_ratio > 0.1:
        warnings.warn(f"⚠️ Ratio NaN élevé : {nan_ratio*100:.1f}%")
    
    # Forward fill NaN (max 3 points)
    lat = pd.Series(lat).ffill(limit=3).bfill(limit=3).fillna(0).values
    lon = pd.Series(lon).ffill(limit=3).bfill(limit=3).fillna(0).values
    speed = pd.Series(speed).ffill(limit=3).bfill(limit=3).fillna(0).values
    
    # 1. CALCUL SEGMENT_DISTANCE (Haversine entre points consécutifs)
    segment_distances = np.zeros(n_points)
    segment_distances[0] = 0.0
    
    for i in range(1, n_points):
        try:
            if (pd.notna(lat[i-1]) and pd.notna(lon[i-1]) and 
                pd.notna(lat[i]) and pd.notna(lon[i])):
                dist = _haversine_distance(float(lat[i-1]), float(lon[i-1]), 
                                          float(lat[i]), float(lon[i]))
                segment_distances[i] = dist if not np.isnan(dist) and not np.isinf(dist) else 0.0
            else:
                segment_distances[i] = 0.0
        except Exception:
            segment_distances[i] = 0.0
    
    df_result['segment_distance'] = segment_distances
    
    # 2. CALCUL CUMULATIVE_DISTANCE
    cumulative_distance = np.cumsum(segment_distances)
    df_result['cumulative_distance'] = cumulative_distance
    
    # 3. CALCUL HEADING (cap)
    heading = np.zeros(n_points)
    heading[0] = 0.0
    
    for i in range(1, n_points):
        try:
            if (pd.notna(lat[i-1]) and pd.notna(lon[i-1]) and 
                pd.notna(lat[i]) and pd.notna(lon[i]) and
                segment_distances[i] > 0.1):
                # Calcul du cap : arctan2(Δlat, Δlon) en degrés
                dlat = lat[i] - lat[i-1]
                dlon = lon[i] - lon[i-1]
                
                # Conversion en mètres (approximation locale)
                lat_mean = (lat[i] + lat[i-1]) / 2
                dlat_m = dlat * np.pi / 180 * EARTH_RADIUS_M
                dlon_m = dlon * np.pi / 180 * EARTH_RADIUS_M * np.cos(np.radians(lat_mean))
                
                heading_rad = np.arctan2(dlat_m, dlon_m)
                heading_deg = np.rad2deg(heading_rad)
                heading_deg = heading_deg % 360
                heading[i] = heading_deg if not np.isnan(heading_deg) else heading[i-1]
            else:
                heading[i] = heading[i-1] if i > 0 else 0.0
        except Exception:
            heading[i] = heading[i-1] if i > 0 else 0.0
    
    # Smoothing heading avec unwrap
    heading = _smooth_heading(heading, window=5)
    df_result['heading'] = heading
    
    # 4. CALCUL CURVATURE (méthode 3-points)
    curvature = np.zeros(n_points)
    
    for i in range(1, n_points - 1):
        try:
            # Ignorer si vitesse trop faible (arrêt/pit)
            if speed[i] < 5.0:
                curvature[i] = 0.0
                continue
            
            # Distance totale sur 3 points
            dist_total = segment_distances[i] + segment_distances[i+1]
            
            if dist_total < 0.1:
                curvature[i] = 0.0
                continue
            
            # Calcul Δheading entre point i-1 et i+1
            heading_prev = np.deg2rad(heading[i-1])
            heading_curr = np.deg2rad(heading[i])
            heading_next = np.deg2rad(heading[i+1])
            
            # Unwrap pour gérer discontinuités
            heading_unwrapped = np.unwrap([heading_prev, heading_curr, heading_next])
            
            delta_heading_rad = abs(heading_unwrapped[2] - heading_unwrapped[0])
            
            if delta_heading_rad > 0.001:
                # Rayon : R = distance / Δheading
                radius = dist_total / delta_heading_rad
                
                if radius > 0 and not np.isnan(radius) and not np.isinf(radius):
                    curvature_value = 1.0 / radius
                    
                    # Signe (gauche = +, droite = -)
                    heading_diff = heading[i+1] - heading[i-1]
                    while heading_diff > 180:
                        heading_diff -= 360
                    while heading_diff < -180:
                        heading_diff += 360
                    
                    sign = 1 if heading_diff > 0 else -1
                    curvature[i] = sign * abs(curvature_value)
                else:
                    curvature[i] = 0.0
            else:
                curvature[i] = 0.0
        except Exception:
            curvature[i] = 0.0
    
    # Filtrer courbures trop faibles (< 0.0001 1/m ≈ rayon > 10km)
    curvature[np.abs(curvature) < 0.0001] = 0.0
    
    # Smooth avec Savitzky-Golay (fenêtre adaptative selon longueur fichier)
    window_curv = max(5, int(n_points / 500))
    if window_curv % 2 == 0:
        window_curv += 1
    window_curv = min(window_curv, len(curvature) - 1 if len(curvature) % 2 == 0 else len(curvature))
    if len(curvature) >= window_curv and window_curv >= 5:
        try:
            curvature = savgol_filter(curvature, window_length=window_curv, polyorder=2, mode='nearest')
        except Exception:
            pass  # Si échec, garder curvature original
    
    # Gérer NaN/Inf
    curvature = np.nan_to_num(curvature, nan=0.0, posinf=0.0, neginf=0.0)
    curvature_series = pd.Series(curvature).ffill(limit=3).fillna(0)
    curvature = curvature_series.values
    df_result['curvature'] = curvature
    
    # 5. CALCUL LATERAL_G (accélération latérale en g)
    lateral_g = np.zeros(n_points)
    
    for i in range(n_points):
        try:
            if pd.notna(curvature[i]) and pd.notna(speed[i]) and speed[i] > 5.0:
                speed_ms = speed[i] / 3.6  # km/h → m/s
                
                # a_y = (v² × curvature) / g (en g)
                if abs(curvature[i]) > 0.0001:
                    lateral_accel_g = (speed_ms ** 2) * abs(curvature[i]) / GRAVITY_MS2
                    
                    # Clamp -3g à +3g (sécurité karting)
                    lateral_accel_g = np.clip(lateral_accel_g, 0, 3.0)
                    
                    # Signe de la courbure
                    lateral_g[i] = np.sign(curvature[i]) * lateral_accel_g
                else:
                    lateral_g[i] = 0.0
            else:
                lateral_g[i] = 0.0
        except Exception:
            lateral_g[i] = 0.0
    
    # Gérer NaN/Inf
    lateral_g = np.nan_to_num(lateral_g, nan=0.0, posinf=0.0, neginf=0.0)
    lateral_g_series = pd.Series(lateral_g).ffill(limit=3).fillna(0)
    lateral_g = lateral_g_series.values
    df_result['lateral_g'] = lateral_g
    
    # 6. THROTTLE/BRAKE INFERENCE (si pas dans CSV)
    if 'throttle' not in df_result.columns or 'brake' not in df_result.columns:
        throttle = np.zeros(n_points)
        brake = np.zeros(n_points)
        
        for i in range(1, n_points):
            try:
                if pd.notna(speed[i]) and pd.notna(speed[i-1]):
                    delta_v = speed[i] - speed[i-1]
                    
                    if delta_v > 0.5:  # Accélération
                        throttle[i] = min(100.0, delta_v * 20)
                        brake[i] = 0.0
                    elif delta_v < -0.5:  # Décélération
                        brake[i] = min(100.0, abs(delta_v) * 20)
                        throttle[i] = 0.0
                    else:  # Coasting
                        throttle[i] = 0.0
                        brake[i] = 0.0
            except Exception:
                throttle[i] = 0.0
                brake[i] = 0.0
        
        df_result['throttle'] = throttle
        df_result['brake'] = brake
    
    return df_result


def detect_laps(df: pd.DataFrame, min_lap_distance_m: float = 100.0) -> pd.DataFrame:
    """
    Détecte les tours en utilisant les Beacon Markers AiM/MoTeC si disponibles.
    Fallback sur détection GPS si pas de beacons.
    
    Avec beacons:
    - lap_number=0 : avant le premier beacon (sortie stands + tour chauffe)
    - lap_number=k : entre le k-ième et (k+1)-ième beacon
    
    Garantit que le Virage 1 des stands (avant 1er beacon) est toujours exclu.
    """
    df_result = df.copy()
    n_points = len(df_result)
    lap_number = np.zeros(n_points, dtype=int)
    
    try:
        # Récupérer le temps
        time_col = None
        for col in ['time', 'Time', 'TIME', 't']:
            if col in df_result.columns:
                time_col = col
                break
        
        if time_col is None:
            df_result['lap_number'] = 1
            return df_result
        
        time_vals = pd.to_numeric(df_result[time_col], errors='coerce').fillna(0).values
        
        # === MÉTHODE 1 : Utiliser les Beacon Markers (AiM/MoTeC) ===
        beacon_markers = df_result.attrs.get('beacon_markers', [])
        
        if beacon_markers and len(beacon_markers) >= 1:
            warnings.warn(f"✓ Utilisation Beacon Markers : {len(beacon_markers)} passages")
            
            # Assigner lap_number basé sur les beacons
            # lap=0 avant le 1er beacon, lap=k entre beacon[k-1] et beacon[k]
            for i in range(n_points):
                t = float(time_vals[i])
                current_lap = 0
                for beacon_idx, beacon_t in enumerate(beacon_markers):
                    if t >= beacon_t:
                        current_lap = beacon_idx + 1
                    else:
                        break
                lap_number[i] = current_lap
            
            df_result['lap_number'] = lap_number
            df_result.attrs['n_laps_detected'] = len(beacon_markers)
            df_result.attrs['method'] = 'beacon_markers'
            
            # Log stats
            lap_0_count = int((lap_number == 0).sum())
            warnings.warn(
                f"✓ Résultat : {len(beacon_markers)} tours, "
                f"{lap_0_count} points en stands/chauffe (lap=0), "
                f"1er tour commence à t={beacon_markers[0]:.3f}s"
            )
            return df_result
        
        # === MÉTHODE 2 : Fallback GPS (si pas de beacons) ===
        warnings.warn("⚠️ Pas de Beacon Markers, utilisation détection GPS")
        
        lat = (df_result['latitude_smooth'].values 
               if 'latitude_smooth' in df_result.columns 
               else df_result['latitude'].values if 'latitude' in df_result.columns
               else None)
        lon = (df_result['longitude_smooth'].values 
               if 'longitude_smooth' in df_result.columns 
               else df_result['longitude'].values if 'longitude' in df_result.columns
               else None)
        
        if lat is None or lon is None:
            df_result['lap_number'] = 1
            return df_result
        
        speed_col = next((c for c in ['speed', 'Speed', 'GPS Speed', 'gps_speed'] 
                         if c in df_result.columns), None)
        speed = pd.to_numeric(df_result[speed_col], errors='coerce').fillna(0).values if speed_col else np.zeros(n_points)
        
        cum_dist = (df_result['cumulative_distance'].values 
                    if 'cumulative_distance' in df_result.columns 
                    else np.zeros(n_points))
        
        # Trouver fin des stands : dernier segment vitesse < 25km/h prolongé
        # puis trouver le 1er passage GPS répété après
        STAND_SPEED = 25.0
        FINISH_RADIUS_M = 25.0
        MIN_LAP_M = min_lap_distance_m
        
        # Trouver quand le kart sort vraiment des stands
        pits_end_idx = 0
        consecutive_fast = 0
        for i in range(n_points):
            if speed[i] > 40.0:
                consecutive_fast += 1
                if consecutive_fast > 50:  # 0.5s @ 100Hz ou 5s @ 10Hz
                    pits_end_idx = max(0, i - 50)
                    break
            else:
                consecutive_fast = 0
        
        if pits_end_idx == 0:
            df_result['lap_number'] = 1
            return df_result
        
        # Trouver la ligne de chrono (point GPS le plus répété après pits_end)
        target_dist = cum_dist[pits_end_idx] + MIN_LAP_M
        candidate_idx = next((i for i in range(pits_end_idx, n_points) 
                             if cum_dist[i] >= target_dist), None)
        
        if candidate_idx is None:
            df_result['lap_number'] = 1
            return df_result
        
        finish_lat = float(lat[candidate_idx])
        finish_lon = float(lon[candidate_idx])
        
        # Numéroter les tours
        current_lap = 0
        last_passage_dist = 0.0
        near_line = False
        
        for i in range(n_points):
            if np.isnan(lat[i]) or np.isnan(lon[i]) or i < pits_end_idx:
                lap_number[i] = current_lap
                continue
            
            dist_to_finish = _haversine_distance(
                float(lat[i]), float(lon[i]), finish_lat, finish_lon)
            dist_since_last = cum_dist[i] - last_passage_dist
            
            if (dist_to_finish < FINISH_RADIUS_M 
                    and dist_since_last > MIN_LAP_M * 0.3
                    and speed[i] > 30.0
                    and not near_line):
                current_lap += 1
                last_passage_dist = cum_dist[i]
                near_line = True
            elif dist_to_finish > FINISH_RADIUS_M * 2.5:
                near_line = False
            
            lap_number[i] = current_lap
        
        df_result['lap_number'] = lap_number
        df_result.attrs['n_laps_detected'] = int(current_lap)
        df_result.attrs['method'] = 'gps_clustering'
        warnings.warn(f"✓ GPS fallback : {current_lap} tours détectés")

    except Exception as e:
        import traceback
        warnings.warn(f"⚠️ Erreur detect_laps : {str(e)}\n{traceback.format_exc()}")
        df_result['lap_number'] = 1
    
    return df_result


def _merge_close_runs(
    vote_array: np.ndarray,
    cumulative_dist_array: np.ndarray,
    max_gap_m: float = 8.0,
) -> np.ndarray:
    """
    Fusionne les runs de True séparés par un gap de <= max_gap_m mètres.
    Universel : fonctionne quel que soit le CSV (10Hz, 25Hz, 100Hz).
    """
    result = vote_array.astype(bool).copy()
    n = len(result)
    if n == 0 or len(cumulative_dist_array) != n:
        return result
    i = 0
    while i < n:
        if result[i]:
            j = i
            while j < n and result[j]:
                j += 1
            k = j
            while k < n and not result[k]:
                k += 1
            if k < n:
                gap_dist = float(cumulative_dist_array[k]) - float(cumulative_dist_array[j])
                if 0 <= gap_dist <= max_gap_m:
                    result[j:k] = True
            i = j
        else:
            i += 1
    return result


def _renumber_corners_by_entry_index(
    corner_details: List[Dict], df_circuit: pd.DataFrame
) -> Dict[int, int]:
    """
    Trie les virages dans l'ordre chronologique du circuit.
    Utilise l'entry_index RELATIF au début de chaque tour (évite le bug quand
    un virage n'a pas le même nombre de tours que les autres).
    Retourne old_id -> new_id.
    """
    if df_circuit is None or "lap_number" not in df_circuit.columns:
        for corner in corner_details:
            corner["_sort_index"] = corner.get("_entry_index_first_lap", float("inf"))
        corner_details.sort(key=lambda c: c.get("_sort_index", float("inf")))
    else:
        lap_starts = {}
        for lap_num in pd.unique(df_circuit["lap_number"]):
            lap_mask = df_circuit["lap_number"] == lap_num
            if lap_mask.any():
                lap_starts[lap_num] = int(df_circuit.index[lap_mask].min())

        for corner in corner_details:
            per_lap = corner.get("per_lap_data", [])
            if not per_lap:
                corner["_sort_index"] = float("inf")
                continue
            relative_indices = []
            for lap_data in per_lap:
                lap_num = lap_data.get("lap")
                entry_idx = lap_data.get("entry_index")
                if (
                    lap_num is not None
                    and entry_idx is not None
                    and lap_num in lap_starts
                ):
                    relative_indices.append(entry_idx - lap_starts[lap_num])
            if relative_indices:
                corner["_sort_index"] = statistics.median(relative_indices)
            else:
                corner["_sort_index"] = float("inf")

        corner_details.sort(key=lambda c: c.get("_sort_index", float("inf")))

    old_to_new = {}
    for i, corner in enumerate(corner_details, start=1):
        old_id = corner.get("id", i)
        old_to_new[old_id] = i
        corner["id"] = i
        corner["corner_id"] = i
        corner["corner_number"] = i
        corner["label"] = f"V{i}"
    return old_to_new


def _avg_spacing_m(cumulative_dist: np.ndarray) -> float:
    """Distance moyenne entre points consécutifs (m)."""
    if len(cumulative_dist) < 2:
        return 0.0
    d = np.diff(np.asarray(cumulative_dist, dtype=float))
    d = d[d > 0]
    return float(np.mean(d)) if len(d) > 0 else 0.0


def _resample_adaptive(
    cumulative_dist: np.ndarray,
    lateral_g: np.ndarray,
    speed: np.ndarray,
    time: Optional[np.ndarray],
    curvature: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray], np.ndarray, str, int]:
    """
    Resampling adaptatif selon densité GPS.
    - avg_spacing < 0.5m (haute densité) : dédensifier à avg_spacing * 4
    - 0.5m <= avg_spacing <= 3m : pas de resampling
    - avg_spacing > 3m : densifier par interpolation linéaire à 2m
    Returns (cum_rs, lateral_g_rs, speed_rs, time_rs, curvature_rs, orig_iloc_rs, strategy, n_after).
    """
    n_orig = len(cumulative_dist)
    total_dist = float(cumulative_dist[-1]) if n_orig > 0 else 0.0
    avg_spacing_m = _avg_spacing_m(cumulative_dist)
    if avg_spacing_m <= 0:
        orig_iloc = np.arange(n_orig)
        return (
            cumulative_dist, lateral_g, speed, time,
            curvature if curvature is not None else None,
            orig_iloc, "none", n_orig
        )

    if avg_spacing_m < 0.5:
        step = avg_spacing_m * 4.0
        strategy = "dedensify"
    elif avg_spacing_m <= 3.0:
        orig_iloc = np.arange(n_orig)
        return (
            cumulative_dist, lateral_g, speed, time,
            curvature, orig_iloc, "none", n_orig
        )
    else:
        step = 2.0
        strategy = "densify"

    if total_dist < step:
        orig_iloc = np.arange(n_orig)
        return (
            cumulative_dist, lateral_g, speed, time,
            curvature, orig_iloc, "none", n_orig
        )

    cum_rs = np.arange(0.0, total_dist + step * 0.5, step)
    n_rs = len(cum_rs)
    lateral_g_rs = np.zeros(n_rs)
    speed_rs = np.zeros(n_rs)
    time_rs = np.zeros(n_rs) if time is not None else None
    curvature_rs = np.zeros(n_rs) if curvature is not None else None
    orig_iloc_rs = np.zeros(n_rs, dtype=int)
    for i in range(n_rs):
        d = cum_rs[i]
        j = int(np.clip(np.searchsorted(cumulative_dist, d, side="left"), 0, len(cumulative_dist) - 1))
        if j > 0 and j < len(cumulative_dist) and (d - cumulative_dist[j - 1]) < (cumulative_dist[j] - d):
            j = j - 1
        orig_iloc_rs[i] = j
        lateral_g_rs[i] = lateral_g[j]
        speed_rs[i] = speed[j]
        if time_rs is not None and time is not None and j < len(time):
            time_rs[i] = time[j]
        if curvature_rs is not None and curvature is not None and j < len(curvature):
            curvature_rs[i] = curvature[j]
    return cum_rs, lateral_g_rs, speed_rs, time_rs, curvature_rs, orig_iloc_rs, strategy, n_rs


def detect_corners(
    df: pd.DataFrame,
    min_lateral_g: float = 0.15,
    min_distance_between_corners: float = 6.0,
    expected_corners: Optional[int] = None,
    laps_analyzed: Optional[int] = None,
) -> pd.DataFrame:
    """
    Détection multi-critères : resampling adaptatif, 3 critères (courbure, lateral_g, vitesse locale),
    validation croisée multi-tours, corner_detail avec per_lap_data.
    """
    required_cols = ['lateral_g', 'speed', 'cumulative_distance']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"❌ Colonnes manquantes : {', '.join(missing_cols)}. Appelez d'abord calculate_trajectory_geometry()")

    if 'lap_number' in df.columns:
        df_circuit = df[df['lap_number'] >= 1].copy()
        if len(df_circuit) < 50:
            df_circuit = df.copy()
    else:
        df_circuit = df.copy()

    df_result = df.copy()
    n_points = len(df_circuit)
    df_result['is_corner'] = False
    df_result['corner_id'] = 0
    df_result['is_apex'] = False
    df_result['corner_type'] = 'straight'

    try:
        lateral_g = np.nan_to_num(pd.to_numeric(df_circuit['lateral_g'], errors='coerce').values, nan=0.0)
        speed = np.nan_to_num(pd.to_numeric(df_circuit['speed'], errors='coerce').values, nan=0.0)
        cumulative_dist = np.nan_to_num(pd.to_numeric(df_circuit['cumulative_distance'], errors='coerce').values, nan=0.0)
        time = pd.to_numeric(df_circuit['time'], errors='coerce').values if 'time' in df_circuit.columns else None
        curvature_arr = pd.to_numeric(df_circuit['curvature'], errors='coerce').values if 'curvature' in df_circuit.columns else None
        if curvature_arr is not None:
            curvature_arr = np.nan_to_num(curvature_arr, nan=0.0)
        has_laps = 'lap_number' in df_circuit.columns
        lap_numbers = df_circuit['lap_number'].values if has_laps else np.ones(n_points, dtype=int)
        if laps_analyzed is None and has_laps:
            laps_analyzed = int(max(1, len(np.unique(lap_numbers))))
        elif laps_analyzed is None:
            laps_analyzed = 1

        # Jonctions de tours (indices où lap_number change)
        if has_laps:
            lap_arr = lap_numbers
            lap_boundaries = set(
                i for i in range(1, len(lap_arr))
                if lap_arr[i] != lap_arr[i - 1]
            )
        else:
            lap_boundaries = set()

        # Reset du signal aux jonctions (fenêtre 8 points de part et d'autre)
        lateral_g = lateral_g.copy()
        n = len(lateral_g)
        for idx in lap_boundaries:
            for offset in range(-8, 9):
                j = idx + offset
                if 0 <= j < n:
                    lateral_g[j] = 0.0
        if curvature_arr is not None:
            curvature_arr = curvature_arr.copy()
            for idx in lap_boundaries:
                for offset in range(-8, 9):
                    j = idx + offset
                    if 0 <= j < n:
                        curvature_arr[j] = 0.0

        import logging
        log = logging.getLogger(__name__)
        log.info("[detect_corners] Jonctions de tours détectées : %s à indices %s", len(lap_boundaries), sorted(lap_boundaries)[:20] if len(lap_boundaries) > 20 else sorted(lap_boundaries))

        avg_spacing_m = _avg_spacing_m(cumulative_dist)
        cum_rs, lateral_g_rs, speed_rs, time_rs, curvature_rs, orig_iloc_rs, resample_strategy, n_after = _resample_adaptive(
            cumulative_dist, lateral_g, speed, time, curvature_arr
        )
        log.info("detect_corners: avg_spacing_m=%.3f strategy=%s n_points_after_resampling=%s", avg_spacing_m, resample_strategy, n_after)

        # Multi-critères
        c1 = np.zeros(len(cum_rs), dtype=bool)
        if curvature_rs is not None:
            curv_abs = np.abs(curvature_rs)
            nonzero = curv_abs[curv_abs > 1e-6]
            if len(nonzero) > 0:
                thresh = float(np.percentile(nonzero, 25))
                c1 = curv_abs > thresh
        c2 = np.abs(lateral_g_rs) > min_lateral_g
        c3 = np.zeros(len(cum_rs), dtype=bool)
        W = 30
        for i in range(W, len(cum_rs) - W):
            before = np.nanmean(speed_rs[i - W:i])
            after = np.nanmean(speed_rs[i + 1:i + W + 1])
            inside = speed_rs[i]
            if before > 1 and after > 1 and inside < 0.97 * min(before, after):
                c3[i] = True
        vote = (c1.astype(int) + c2.astype(int) + c3.astype(int)) >= 2
        vote = _merge_close_runs(vote, cum_rs, max_gap_m=8.0)
        labeled_vote, num_runs = label(vote)
        is_corner_zone = np.zeros(len(vote), dtype=bool)
        for rid in range(1, num_runs + 1):
            run_mask = labeled_vote == rid
            if np.sum(run_mask) >= 4:
                is_corner_zone[run_mask] = True

        if not is_corner_zone.any():
            df_result.attrs['corners'] = {'total_corners': 0, 'total_distance_m': float(cumulative_dist[-1]) if len(cumulative_dist) > 0 else 0.0, 'avg_speed_kmh': 0.0, 'max_lateral_g': 0.0, 'corner_details': []}
            return df_result

        labeled_array, num_features = label(is_corner_zone)
        valid_corners = []
        for cid in range(1, num_features + 1):
            corner_mask = labeled_array == cid
            idx_rs = np.where(corner_mask)[0]
            if len(idx_rs) < 2:
                continue
            start_rs, end_rs = int(idx_rs[0]), int(idx_rs[-1])
            if end_rs >= len(cum_rs) or cum_rs[end_rs] - cum_rs[start_rs] < MIN_CORNER_DISTANCE_M:
                continue
            if time_rs is not None and end_rs < len(time_rs) and start_rs < len(time_rs) and (time_rs[end_rs] - time_rs[start_rs]) < MIN_CORNER_DURATION_S:
                continue
            indices_orig = np.array([int(orig_iloc_rs[i]) for i in idx_rs], dtype=int)
            start_orig = int(orig_iloc_rs[start_rs])
            end_orig = int(orig_iloc_rs[end_rs])
            g_vals = np.abs([lateral_g[i] for i in indices_orig if i < len(lateral_g)])
            if len(g_vals) > 0 and np.max(g_vals) < min_lateral_g:
                continue
            apex_local = np.argmax(np.abs([lateral_g[i] for i in indices_orig if i < len(lateral_g)]))
            apex_orig = int(indices_orig[apex_local])
            valid_corners.append({'id': cid, 'indices': indices_orig, 'start': start_orig, 'end': end_orig, 'apex': apex_orig})

        def _merge_by_min_dist(corners: List[Dict], cum_dist: np.ndarray, min_d: float, lap_boundaries_set: Optional[set] = None) -> tuple:
            """Retourne (liste fusionnée, nombre de fusions bloquées par jonction)."""
            if not corners or min_d <= 0:
                return corners, 0
            lap_boundaries_set = lap_boundaries_set or set()
            out = []
            n_blocked = 0
            i = 0
            while i < len(corners):
                cur = dict(corners[i])
                cur['indices'] = list(cur['indices'])
                cur.setdefault('apex', cur['end'])
                j = i + 1
                while j < len(corners):
                    e1, s2 = cur['end'], corners[j]['start']
                    gap = set(range(e1 + 1, s2)) if e1 + 1 < s2 else set()
                    if lap_boundaries_set and gap & lap_boundaries_set:
                        n_blocked += 1
                        break
                    if e1 < len(cum_dist) and s2 < len(cum_dist) and (cum_dist[s2] - cum_dist[e1]) < min_d:
                        cur['end'] = corners[j]['end']
                        cur['indices'] = sorted(set(cur['indices']) | set(corners[j]['indices']))
                        j += 1
                        continue
                    break
                cur['indices'] = np.array(cur['indices'])
                out.append(cur)
                i = j
            return out, n_blocked

        n_merge_blocked = 0
        if expected_corners is not None and expected_corners >= 1:
            lo, hi = 3.0, 40.0
            for _ in range(15):
                mid = (lo + hi) * 0.5
                m, nb = _merge_by_min_dist(valid_corners, cumulative_dist, mid, lap_boundaries)
                if len(m) == expected_corners:
                    min_distance_between_corners = round(mid, 1)
                    valid_corners = m
                    n_merge_blocked = nb
                    break
                if len(m) > expected_corners:
                    hi = mid
                else:
                    lo = mid
            else:
                valid_corners, n_merge_blocked = _merge_by_min_dist(valid_corners, cumulative_dist, min_distance_between_corners, lap_boundaries)
        else:
            valid_corners, n_merge_blocked = _merge_by_min_dist(valid_corners, cumulative_dist, min_distance_between_corners, lap_boundaries)
        log.info("[detect_corners] Fusions bloquées par jonction : %s", n_merge_blocked)

        coherence_radius_m = 30.0
        min_laps_confirm = max(1, laps_analyzed // 2)
        segments_with_lap_and_apex = []
        for c in valid_corners:
            indices = c['indices']
            lap_nums = [int(lap_numbers[i]) for i in indices if i < len(lap_numbers)]
            lap_num = int(np.bincount(lap_nums).argmax()) if lap_nums else 1
            start_idx = c['start']
            end_idx = c['end']
            apex_local = np.argmax(np.abs([lateral_g[i] for i in indices]))
            apex_index = int(indices[apex_local])
            apex_lat, apex_lon = _get_apex_gps(df_circuit, list(indices))
            segments_with_lap_and_apex.append({
                'lap': lap_num, 'indices': indices, 'start': start_idx, 'end': end_idx,
                'apex_index': apex_index, 'apex_lat': apex_lat, 'apex_lon': apex_lon,
                'lateral_g': lateral_g, 'speed': speed, 'cumulative_dist': cumulative_dist, 'time': time,
            })

        clusters = []
        used = [False] * len(segments_with_lap_and_apex)
        for i, s in enumerate(segments_with_lap_and_apex):
            if used[i]:
                continue
            lat1, lon1 = s['apex_lat'], s['apex_lon']
            if lat1 is None or lon1 is None:
                continue
            cluster = [s]
            used[i] = True
            for j in range(i + 1, len(segments_with_lap_and_apex)):
                if used[j]:
                    continue
                s2 = segments_with_lap_and_apex[j]
                lat2, lon2 = s2['apex_lat'], s2['apex_lon']
                if lat2 is None or lon2 is None:
                    continue
                if _haversine_distance(lat1, lon1, lat2, lon2) < coherence_radius_m:
                    cluster.append(s2)
                    used[j] = True
            laps_in_cluster = len(set(seg['lap'] for seg in cluster))
            if laps_in_cluster >= min_laps_confirm:
                clusters.append(cluster)

        corner_details = []
        physical_id = 0
        for cluster in clusters:
            physical_id += 1
            per_lap_data = []
            apex_lats = []
            apex_lons = []
            entry_speeds = []
            apex_speeds = []
            exit_speeds = []
            max_gs = []
            time_losts = []
            entry_indices = []
            apex_indices = []
            exit_indices = []
            corner_type = "left"
            for seg in cluster:
                lap_num = seg['lap']
                idx = seg['indices']
                start_idx, end_idx = seg['start'], seg['end']
                apex_idx = seg['apex_index']
                lat, lon = seg['apex_lat'], seg['apex_lon']
                if lat is not None:
                    apex_lats.append(lat)
                if lon is not None:
                    apex_lons.append(lon)
                spd = seg['speed']
                entry_speeds.append(float(spd[start_idx]) if start_idx < len(spd) else 0.0)
                apex_speeds.append(float(spd[apex_idx]) if apex_idx < len(spd) else 0.0)
                exit_speeds.append(float(spd[end_idx]) if end_idx < len(spd) else 0.0)
                g_vals = np.abs([seg['lateral_g'][k] for k in idx if k < len(seg['lateral_g'])])
                max_gs.append(float(np.max(g_vals)) if len(g_vals) > 0 else 0.0)
                time_losts.append(0.0)
                entry_indices.append(int(df_circuit.index[start_idx]))
                apex_indices.append(int(df_circuit.index[apex_idx]))
                exit_indices.append(int(df_circuit.index[end_idx]))
                if curvature_arr is not None and len(idx) > 0:
                    curv_in = curvature_arr[idx]
                    corner_type = "left" if np.nanmean(curv_in) > 0 else "right"
                per_lap_data.append({
                    'lap': lap_num, 'apex_lat': lat, 'apex_lon': lon,
                    'entry_index': entry_indices[-1], 'apex_index': apex_indices[-1], 'exit_index': exit_indices[-1],
                    'entry_speed_kmh': entry_speeds[-1], 'apex_speed_kmh': apex_speeds[-1], 'exit_speed_kmh': exit_speeds[-1],
                    'max_lateral_g': max_gs[-1], 'time_lost': time_losts[-1],
                })
            n_laps = len(cluster)
            apex_lat_avg = float(np.mean(apex_lats)) if apex_lats else None
            apex_lon_avg = float(np.mean(apex_lons)) if apex_lons else None
            if apex_lat_avg is not None and apex_lon_avg is not None and len(apex_lats) > 1:
                mean_dist = np.mean([_haversine_distance(apex_lat_avg, apex_lon_avg, la, lo) for la, lo in zip(apex_lats, apex_lons)])
                consistency_score = max(0.0, min(1.0, 1.0 - mean_dist / coherence_radius_m))
            else:
                consistency_score = 1.0
            apex_dists = [cumulative_dist[seg['apex_index']] for seg in cluster if seg['apex_index'] < len(cumulative_dist)]
            avg_cum_dist = float(np.mean(apex_dists)) if apex_dists else 0.0
            min_cum_dist = float(min(apex_dists)) if apex_dists else 0.0
            first_lap_in_cluster = min(seg['lap'] for seg in cluster)
            entry_on_first_lap = [p['entry_index'] for p in per_lap_data if p.get('lap') == first_lap_in_cluster]
            entry_index_first_lap = min(entry_on_first_lap) if entry_on_first_lap else float('inf')
            ref = cluster[0]
            corner_details.append({
                'id': physical_id,
                'avg_cumulative_distance': avg_cum_dist,
                'min_cumulative_distance': min_cum_dist,
                '_entry_index_first_lap': entry_index_first_lap,
                'lap': ref['lap'],
                'label': f"V{physical_id}",
                'type': corner_type,
                'entry_index': entry_indices[0],
                'apex_index': apex_indices[0],
                'exit_index': exit_indices[0],
                'apex_lat': apex_lat_avg,
                'apex_lon': apex_lon_avg,
                'entry_speed_kmh': float(np.mean(entry_speeds)) if entry_speeds else 0.0,
                'apex_speed_kmh': float(np.mean(apex_speeds)) if apex_speeds else 0.0,
                'exit_speed_kmh': float(np.mean(exit_speeds)) if exit_speeds else 0.0,
                'max_lateral_g': float(np.mean(max_gs)) if max_gs else 0.0,
                'distance_m': float(ref['cumulative_dist'][ref['end']] - ref['cumulative_dist'][ref['start']]) if ref['end'] < len(ref['cumulative_dist']) else 0.0,
                'duration_s': 0.0,
                'confirmed_in_laps': n_laps,
                'consistency_score': round(consistency_score, 3),
                'per_lap_data': per_lap_data,
            })

            for seg in cluster:
                for idx in seg['indices']:
                    if idx < len(df_circuit):
                        oi = df_circuit.index[idx]
                        df_result.at[oi, 'is_corner'] = True
                        df_result.at[oi, 'corner_id'] = physical_id
                        df_result.at[oi, 'corner_type'] = corner_type
                        df_result.at[oi, 'lap_number'] = seg['lap']
                apex_idx = seg['apex_index']
                if apex_idx < len(df_circuit):
                    df_result.at[df_circuit.index[apex_idx], 'is_apex'] = True

        # Ordre de passage : tri par entry_index RELATIF au début de chaque tour (median)
        old_to_new = _renumber_corners_by_entry_index(corner_details, df_circuit)
        log.info(
            "[detect_corners] Ordre par entry_index relatif (median) : %s",
            [f"V{c['id']} sort_idx={c.get('_sort_index', '?')}" for c in corner_details],
        )
        for idx in df_result.index:
            if df_result.at[idx, 'is_corner']:
                old = df_result.at[idx, 'corner_id']
                df_result.at[idx, 'corner_id'] = old_to_new.get(old, old)
        log.info(
            "[detect_corners] Virages finaux : %s → %s",
            len(corner_details),
            [f"V{c['id']} d={c.get('avg_cumulative_distance', 0):.0f}m" for c in corner_details],
        )

        total_distance = float(cumulative_dist[-1]) if len(cumulative_dist) > 0 else 0.0
        avg_speed = float(np.mean(speed[speed > 0])) if np.any(speed > 0) else 0.0
        max_lateral_g_global = float(np.max(np.abs(lateral_g))) if len(lateral_g) > 0 else 0.0
        df_result.attrs['corners'] = {
            'total_corners': len(corner_details),
            'total_distance_m': total_distance,
            'avg_speed_kmh': avg_speed,
            'max_lateral_g': max_lateral_g_global,
            'corner_details': corner_details
        }
    except Exception as e:
        warnings.warn(f"⚠️ Erreur détection virages : {str(e)}")
        df_result.attrs['corners'] = {'total_corners': 0, 'total_distance_m': 0.0, 'avg_speed_kmh': 0.0, 'max_lateral_g': 0.0, 'corner_details': []}
    return df_result


def calculate_optimal_trajectory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule la trajectoire optimale basée sur la physique (vitesse apex optimale).
    
    Pour chaque virage, calcule la vitesse apex optimale basée sur :
    - Rayon de courbure moyen
    - Coefficient de friction (karting slick)
    - Physique : v_optimal = sqrt(μ × g × R)
    
    Args:
        df: DataFrame avec colonnes 'corner_id', 'curvature', 'speed'
            (doit avoir été traité par detect_corners())
    
    Returns:
        DataFrame enrichi avec colonnes :
        - 'optimal_speed_kmh' : vitesse apex optimale (NaN si ligne droite ou invalide)
    
        Met à jour df.attrs['corners'][i] avec :
        - 'optimal_apex_speed_kmh' : float
        - 'speed_efficiency_pct' : float (apex_speed / optimal * 100)
    
    Raises:
        ValueError: Si colonnes requises manquantes
    """
    if 'corner_id' not in df.columns or 'curvature' not in df.columns:
        raise ValueError("❌ Colonnes manquantes. Appelez d'abord detect_corners()")
    
    df_result = df.copy()
    n_points = len(df_result)
    
    # Initialiser colonnes
    df_result['optimal_speed_kmh'] = np.nan
    
    try:
        speed = pd.to_numeric(df_result['speed'], errors='coerce').values
        curvature = pd.to_numeric(df_result['curvature'], errors='coerce').values
        corner_id = df_result['corner_id'].values
        
        # Parcourir chaque virage
        if 'corners' in df_result.attrs and 'corner_details' in df_result.attrs['corners']:
            corner_details = df_result.attrs['corners']['corner_details']
            
            for corner_info in corner_details:
                corner_id_val = corner_info['id']
                apex_index = corner_info['apex_index']
                
                # Calculer rayon moyen du virage
                corner_mask = corner_id == corner_id_val
                curvature_in_corner = curvature[corner_mask]
                curvature_valid = curvature_in_corner[~np.isnan(curvature_in_corner)]
                
                if len(curvature_valid) == 0:
                    continue
                
                curvature_mean = np.mean(np.abs(curvature_valid))
                
                if curvature_mean > 0.0001:
                    # Rayon : R = 1 / curvature
                    radius = 1.0 / curvature_mean
                    
                    if radius > 0 and not np.isnan(radius) and not np.isinf(radius):
                        # Vitesse optimale : v = sqrt(μ × g × R)
                        v_optimal_ms = np.sqrt(FRICTION_COEFF * GRAVITY_MS2 * radius)
                        v_optimal_kmh = v_optimal_ms * 3.6
                        
                        # Validation : 30 < v_optimal < 150 km/h
                        if 30.0 < v_optimal_kmh < 150.0:
                            # Remplir colonnes pour tous les points du virage
                            for idx in np.where(corner_mask)[0]:
                                if idx < n_points:
                                    df_result.at[df_result.index[idx], 'optimal_speed_kmh'] = v_optimal_kmh
                            
                            # Mettre à jour métadonnées
                            apex_speed = corner_info['apex_speed_kmh']
                            if v_optimal_kmh > 0:
                                speed_efficiency = (apex_speed / v_optimal_kmh) * 100
                            else:
                                speed_efficiency = 0.0
                            
                            corner_info['optimal_apex_speed_kmh'] = float(v_optimal_kmh)
                            corner_info['speed_efficiency_pct'] = float(speed_efficiency)
            
            # Mettre à jour attrs
            df_result.attrs['corners']['corner_details'] = corner_details
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur calcul trajectoire optimale : {str(e)}")
    
    return df_result
