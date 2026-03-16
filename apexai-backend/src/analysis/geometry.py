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


def _project_corner_on_lap_trace(
    apex_lat: float,
    apex_lon: float,
    lap_lats: np.ndarray,
    lap_lons: np.ndarray,
    lap_cum_dist: np.ndarray,
) -> float:
    """
    Project a corner's apex GPS position onto a single-lap GPS trace.
    Returns the curvilinear distance (arc-length) along that lap trace
    at the point closest to the corner apex.
    """
    min_dist = float("inf")
    best_cum = 0.0
    for i in range(len(lap_lats)):
        d = _haversine_distance(apex_lat, apex_lon, float(lap_lats[i]), float(lap_lons[i]))
        if d < min_dist:
            min_dist = d
            best_cum = float(lap_cum_dist[i])
    return best_cum


def _renumber_corners_by_entry_index(
    corner_details: List[Dict], df_circuit: pd.DataFrame
) -> Dict[int, int]:
    """
    Sort corners in physical circuit order using GPS curvilinear projection.

    Strategy:
    1. Pick ONE reference lap from df_circuit (the first lap with most points).
    2. Extract its GPS trace and compute cumulative arc-length.
    3. For each corner, project its average apex (lat, lon) onto the reference
       lap trace → gives a curvilinear distance along one lap.
    4. Sort corners by that distance → physically correct order regardless of
       how many laps each corner was detected on.

    Falls back to relative entry_index if GPS columns are missing.
    Returns old_id -> new_id mapping.
    """
    import logging
    log = logging.getLogger(__name__)

    lat_col = (
        "latitude_smooth"
        if df_circuit is not None and "latitude_smooth" in df_circuit.columns
        else "latitude"
    )
    lon_col = (
        "longitude_smooth"
        if df_circuit is not None and "longitude_smooth" in df_circuit.columns
        else "longitude"
    )

    gps_available = (
        df_circuit is not None
        and "lap_number" in df_circuit.columns
        and lat_col in df_circuit.columns
        and lon_col in df_circuit.columns
    )

    if gps_available:
        # --- Pick the reference lap: the one with the MOST data points ---
        lap_counts = df_circuit["lap_number"].value_counts()
        # Exclude lap 0 (pit/warmup)
        lap_counts = lap_counts[lap_counts.index >= 1]
        if len(lap_counts) == 0:
            gps_available = False

    if gps_available:
        ref_lap = int(lap_counts.idxmax())
        lap_mask = df_circuit["lap_number"] == ref_lap
        df_ref = df_circuit.loc[lap_mask].copy()

        ref_lats = pd.to_numeric(df_ref[lat_col], errors="coerce").ffill().bfill().values
        ref_lons = pd.to_numeric(df_ref[lon_col], errors="coerce").ffill().bfill().values

        # Compute cumulative arc-length along the reference lap
        ref_cum_dist = np.zeros(len(ref_lats))
        for i in range(1, len(ref_lats)):
            ref_cum_dist[i] = ref_cum_dist[i - 1] + _haversine_distance(
                float(ref_lats[i - 1]), float(ref_lons[i - 1]),
                float(ref_lats[i]), float(ref_lons[i]),
            )

        log.info(
            "[_renumber] Using GPS projection on ref lap %d (%d pts, %.0f m)",
            ref_lap, len(ref_lats), ref_cum_dist[-1] if len(ref_cum_dist) > 0 else 0,
        )

        for corner in corner_details:
            apex_lat = corner.get("apex_lat")
            apex_lon = corner.get("apex_lon")
            if apex_lat is not None and apex_lon is not None:
                proj_dist = _project_corner_on_lap_trace(
                    apex_lat, apex_lon, ref_lats, ref_lons, ref_cum_dist,
                )
                corner["_sort_index"] = proj_dist
            else:
                corner["_sort_index"] = float("inf")

        corner_details.sort(key=lambda c: c.get("_sort_index", float("inf")))
        log.info(
            "[_renumber] GPS-projected order: %s",
            [f"old_id={c.get('id')} proj={c.get('_sort_index', '?'):.1f}m" for c in corner_details],
        )
    else:
        # Fallback: relative entry_index (original method)
        if df_circuit is not None and "lap_number" in df_circuit.columns:
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
        else:
            for corner in corner_details:
                corner["_sort_index"] = corner.get("_entry_index_first_lap", float("inf"))

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
    min_lateral_g: float = 0.5,
    min_distance_between_corners: float = 8.0,
    expected_corners: Optional[int] = None,
    laps_analyzed: Optional[int] = None,
    curvature_threshold_override: Optional[float] = None,
) -> pd.DataFrame:
    """
    Détection de virages mathématique via scipy.signal.find_peaks sur la courbure et le G latéral.
    Remplace l'ancienne logique complexe par une approche de traitement du signal propre.
    """
    from scipy.signal import find_peaks
    import logging
    
    log = logging.getLogger(__name__)

    # Vérifications de base
    required_cols = ['lateral_g', 'speed', 'cumulative_distance']
    if not all(col in df.columns for col in required_cols):
        raise ValueError(f"❌ Colonnes manquantes dans le DataFrame. Requis: {required_cols}")

    df_result = df.copy()
    n_points = len(df_result)
    
    # Init des colonnes de sortie
    df_result['is_corner'] = False
    df_result['corner_id'] = 0
    df_result['is_apex'] = False
    df_result['corner_type'] = 'straight'

    if n_points < 10:
        df_result.attrs['corners'] = {'total_corners': 0, 'corner_details': []}
        return df_result

    try:
        cumulative_dist = np.nan_to_num(pd.to_numeric(df_result['cumulative_distance'], errors='coerce').values, nan=0.0)
        lateral_g = np.nan_to_num(pd.to_numeric(df_result['lateral_g'], errors='coerce').values, nan=0.0)
        speed = np.nan_to_num(pd.to_numeric(df_result['speed'], errors='coerce').values, nan=0.0)
        
        has_laps = 'lap_number' in df_result.columns
        lap_numbers = df_result['lap_number'].values if has_laps else np.ones(n_points, dtype=int)
        
        # Le signal principal est la valeur absolue du G latéral (lissé dans calculate_trajectory_geometry)
        signal = np.abs(lateral_g)
        
        # Trouver les pics de G latéral (Apex potentiels)
        # On force une distance beaucoup plus grande (ex: 25-30m) pour fusionner les doubles apex
        effective_min_dist = max(min_distance_between_corners, 25.0)
        avg_spacing = _avg_spacing_m(cumulative_dist)
        if avg_spacing > 0:
            distance_samples = max(2, int(effective_min_dist / avg_spacing))
        else:
            distance_samples = 25
            
        # Trouver les pics (Apexes)
        peaks, properties = find_peaks(
            signal,
            height=min_lateral_g,       # Minimum G latéral pour être un virage
            distance=distance_samples,  # Distance minimale augmentée entre deux apexes
            prominence=0.25             # Le pic doit ressortir d'au moins 0.25g pour filtrer les faux virages
        )
        
        log.info(f"detect_corners (find_peaks): {len(peaks)} apex potentiels trouvés (seuil {min_lateral_g}g, dist {effective_min_dist}m)")
        
        # Création des zones de virages autour des peaks trouvés
        is_corner_zone = np.zeros(n_points, dtype=bool)
        
        # Définir l'étendue d'un virage (ex: G > seuil autour de l'apex)
        threshold_entry_exit = max(0.2, min_lateral_g * 0.4) # zone où G > 40% de l'apex ou > 0.2
        
        valid_apexes = []
        for p in peaks:
            lap_num = lap_numbers[p]
            if lap_num == 0 and has_laps:
                continue # Ignore les virages du tour de chauffe/sortie des stands
                
            # Chercher le début (reculer jusqu'à ce que le G passe sous le seuil)
            start_idx = p
            while start_idx > 0 and signal[start_idx] > threshold_entry_exit and lap_numbers[start_idx] == lap_num:
                start_idx -= 1
                
            # Chercher la fin (avancer)
            end_idx = p
            while end_idx < n_points - 1 and signal[end_idx] > threshold_entry_exit and lap_numbers[end_idx] == lap_num:
                end_idx += 1
                
            # Vérifier la validité de la zone
            dist_zone = cumulative_dist[end_idx] - cumulative_dist[start_idx]
            if dist_zone >= 1.0: # Au moins 1 mètre de long
                is_corner_zone[start_idx:end_idx+1] = True
                valid_apexes.append({
                    'peak_idx': p,
                    'start_idx': start_idx,
                    'end_idx': end_idx,
                    'lap': lap_num
                })

        # Regrouper par numéro de virage physique (Cluster by physical location on track)
        # On projete tous les apex sur le premier tour chronométré complet pour trouver leur numéro
        
        corner_details = []
        
        if not valid_apexes:
            df_result.attrs['corners'] = {'total_corners': 0, 'corner_details': []}
            return df_result
            
        # --- Numérotation physique des virages ---
        # 1. Regrouper les apex réels proches spatialement
        # Augmentation forte du rayon de cohérence pour grouper les pif-pafs serrés ou doubles apex sous le même V
        coherence_radius_m = min_distance_between_corners * 2.5
        clusters = []
        used = [False] * len(valid_apexes)
        
        for i, a1 in enumerate(valid_apexes):
            if used[i]:
                continue
            
            lat1, lon1 = _get_apex_gps(df_result, [a1['peak_idx']])
            if lat1 is None:
                continue
                
            cluster = [a1]
            used[i] = True
            
            for j in range(i + 1, len(valid_apexes)):
                if used[j]:
                    continue
                a2 = valid_apexes[j]
                lat2, lon2 = _get_apex_gps(df_result, [a2['peak_idx']])
                
                if lat2 is not None and _haversine_distance(lat1, lon1, lat2, lon2) < coherence_radius_m:
                    cluster.append(a2)
                    used[j] = True
                    
            clusters.append(cluster)
            
        # 2. Filtrer les faux positifs (virage présent que sur 1 tour sur N)
        min_laps_to_confirm = max(1, (laps_analyzed or 1) // 3)
        valid_clusters = [c for c in clusters if len(set(a['lap'] for a in c)) >= min_laps_to_confirm]
        
        if not valid_clusters:
            # Fallback si on a tout filtré
            valid_clusters = clusters
            
        log.info(f"detect_corners: {len(valid_clusters)} virages physiques confirmés")
        
        # 3. Construire le corner_details = JSON attendu par le front
        
        for physical_id, cluster in enumerate(valid_clusters, start=1):
            per_lap_data = []
            
            # Calculs moyens
            entry_speeds = []
            apex_speeds = []
            exit_speeds = []
            max_gs = []
            apex_lats = []
            apex_lons = []
            corner_type = "straight"
            
            for a in cluster:
                # Type basé sur la courbure du peak
                if 'curvature' in df_result.columns:
                    curv = df_result['curvature'].iloc[a['peak_idx']]
                    # + = gauche, - = droite
                    local_type = "left" if curv > 0 else "right"
                    if corner_type == "straight":
                        corner_type = local_type
                
                lat, lon = _get_apex_gps(df_result, [a['peak_idx']])
                if lat: apex_lats.append(lat)
                if lon: apex_lons.append(lon)
                
                entry_speeds.append(speed[a['start_idx']])
                apex_speeds.append(speed[a['peak_idx']])
                exit_speeds.append(speed[a['end_idx']])
                max_gs.append(signal[a['peak_idx']])
                
                # Update df_result
                df_result.loc[a['start_idx']:a['end_idx'], 'is_corner'] = True
                df_result.loc[a['start_idx']:a['end_idx'], 'corner_id'] = physical_id
                df_result.loc[a['start_idx']:a['end_idx'], 'corner_type'] = local_type if 'curvature' in df_result.columns else "unknown"
                df_result.at[df_result.index[a['peak_idx']], 'is_apex'] = True
                
                per_lap_data.append({
                    'lap': a['lap'],
                    'apex_lat': lat,
                    'apex_lon': lon,
                    'entry_index': int(df_result.index[a['start_idx']]),
                    'apex_index': int(df_result.index[a['peak_idx']]),
                    'exit_index': int(df_result.index[a['end_idx']]),
                    'entry_speed_kmh': float(speed[a['start_idx']]),
                    'apex_speed_kmh': float(speed[a['peak_idx']]),
                    'exit_speed_kmh': float(speed[a['end_idx']]),
                    'max_lateral_g': float(signal[a['peak_idx']]),
                    'time_lost': 0.0 # Rempli par performance_metrics
                })
            
            # Représentant global du virage (moyenne sur tous les tours)
            ref_idx = cluster[0]['peak_idx']
            first_entry_index = int(df_result.index[cluster[0]['start_idx']])
            
            corner_details.append({
                'id': physical_id,
                'corner_id': physical_id,
                'corner_number': physical_id,
                'label': f"V{physical_id}",
                'type': corner_type,
                '_sort_index': cluster[0]['start_idx'], # Pour le tri physique ensuite
                
                'entry_index': first_entry_index,
                'apex_index': int(df_result.index[ref_idx]),
                'exit_index': int(df_result.index[cluster[0]['end_idx']]),
                
                'apex_lat': float(np.mean(apex_lats)) if apex_lats else None,
                'apex_lon': float(np.mean(apex_lons)) if apex_lons else None,
                
                'entry_speed_kmh': float(np.mean(entry_speeds)) if entry_speeds else 0.0,
                'apex_speed_kmh': float(np.mean(apex_speeds)) if apex_speeds else 0.0,
                'exit_speed_kmh': float(np.mean(exit_speeds)) if exit_speeds else 0.0,
                'max_lateral_g': float(np.mean(max_gs)) if max_gs else 0.0,
                
                'confirmed_in_laps': len(cluster),
                'per_lap_data': per_lap_data
            })

        # 4. Trier physiquement (Re-numbering)
        # On va utiliser le _renumber_corners_by_entry_index (qui existe déjà et est propre)
        old_to_new = _renumber_corners_by_entry_index(corner_details, df_result)
        
        # Mettre à jour df_result avec les nouveaux IDs triés
        for idx in df_result.index:
            if df_result.at[idx, 'is_corner']:
                old_id = df_result.at[idx, 'corner_id']
                df_result.at[idx, 'corner_id'] = old_to_new.get(old_id, old_id)

        # 5. Metadata attachées
        df_result.attrs['corners'] = {
            'total_corners': len(corner_details),
            'corner_details': corner_details
        }
        
    except Exception as e:
        import traceback
        warnings.warn(f"⚠️ Erreur critique dans detect_corners (fallback return empty): {str(e)}\n{traceback.format_exc()}")
        df_result.attrs['corners'] = {'total_corners': 0, 'corner_details': []}

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
