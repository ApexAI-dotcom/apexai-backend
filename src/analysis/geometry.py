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
    
    # Smooth avec Savitzky-Golay
    if len(curvature) >= 11:
        try:
            curvature = savgol_filter(curvature, window_length=11, polyorder=2, mode='nearest')
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


def detect_corners(
    df: pd.DataFrame,
    min_lateral_g: float = MIN_CORNER_LATERAL_G
) -> pd.DataFrame:
    """
    Détecte les virages et identifie les apex avec précision F1-level.
    
    Algorithme :
    1. Identifie zones où |lateral_g| > min_lateral_g
    2. Groupe segments avec scipy.ndimage.label()
    3. Filtre par durée et distance minimum
    4. Trouve apex = point de |lateral_g| max
    
    Args:
        df: DataFrame avec colonnes 'lateral_g', 'speed', 'cumulative_distance'
            Optionnel : 'time' pour durée
        min_lateral_g: Seuil minimum d'accélération latérale pour virage (g)
    
    Returns:
        DataFrame enrichi avec colonnes :
        - 'is_corner' : bool
        - 'corner_id' : int (1-indexed, 0 = ligne droite)
        - 'is_apex' : bool
        - 'corner_type' : "left" | "right" | "straight"
        
        Métadonnées dans df.attrs['corners']
    
    Raises:
        ValueError: Si colonnes requises manquantes
    """
    # Validation colonnes requises
    required_cols = ['lateral_g', 'speed', 'cumulative_distance']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        raise ValueError(f"❌ Colonnes manquantes : {', '.join(missing_cols)}. Appelez d'abord calculate_trajectory_geometry()")
    
    df_result = df.copy()
    n_points = len(df_result)
    
    # Initialiser colonnes
    df_result['is_corner'] = False
    df_result['corner_id'] = 0
    df_result['is_apex'] = False
    df_result['corner_type'] = 'straight'
    
    try:
        lateral_g = pd.to_numeric(df_result['lateral_g'], errors='coerce').values
        speed = pd.to_numeric(df_result['speed'], errors='coerce').values
        cumulative_dist = pd.to_numeric(df_result['cumulative_distance'], errors='coerce').values
        
        if 'time' in df_result.columns:
            time = pd.to_numeric(df_result['time'], errors='coerce').values
        else:
            time = None
        
        # Gérer NaN
        lateral_g = np.nan_to_num(lateral_g, nan=0.0)
        cumulative_dist = np.nan_to_num(cumulative_dist, nan=0.0)
        
        # 1. IDENTIFICATION ZONES VIRAGE : |lateral_g| > min_lateral_g
        is_corner_zone = np.abs(lateral_g) > min_lateral_g
        
        if not is_corner_zone.any():
            df_result.attrs['corners'] = {
                'total_corners': 0,
                'total_distance_m': float(cumulative_dist[-1]) if len(cumulative_dist) > 0 else 0.0,
                'avg_speed_kmh': 0.0,
                'max_lateral_g': 0.0,
                'corner_details': []
            }
            return df_result
        
        # 2. GROUPER SEGMENTS AVEC scipy.ndimage.label()
        labeled_array, num_features = label(is_corner_zone)
        
        # 3. FILTRER VIRAGES PAR DURÉE ET DISTANCE
        valid_corners = []
        corner_details = []
        
        for corner_id in range(1, num_features + 1):
            corner_mask = labeled_array == corner_id
            corner_indices = np.where(corner_mask)[0]
            
            if len(corner_indices) < 2:
                continue
            
            start_idx = int(corner_indices[0])
            end_idx = int(corner_indices[-1])
            
            # Vérifier distance
            if start_idx < len(cumulative_dist) and end_idx < len(cumulative_dist):
                corner_distance = cumulative_dist[end_idx] - cumulative_dist[start_idx]
                if corner_distance < MIN_CORNER_DISTANCE_M:
                    continue
            else:
                continue
            
            # Vérifier durée (si time disponible)
            if time is not None:
                if start_idx < len(time) and end_idx < len(time):
                    if pd.notna(time[start_idx]) and pd.notna(time[end_idx]):
                        duration = float(time[end_idx] - time[start_idx])
                        if duration < MIN_CORNER_DURATION_S:
                            continue
            
            valid_corners.append({
                'id': corner_id,
                'indices': corner_indices,
                'start': start_idx,
                'end': end_idx
            })
        
        # 4. TRAITER CHAQUE VIRAGE VALIDE
        for corner_info in valid_corners:
            corner_id = corner_info['id']
            corner_indices = corner_info['indices']
            start_idx = corner_info['start']
            end_idx = corner_info['end']
            
            # Type de virage (gauche/droite) - utiliser curvature si disponible
            if 'curvature' in df_result.columns:
                curvature_in_corner = df_result.loc[df_result.index[corner_indices], 'curvature'].values
                curvature_mean = np.mean(curvature_in_corner) if len(curvature_in_corner) > 0 else 0.0
                corner_type = "left" if curvature_mean > 0 else "right"
            else:
                # Fallback : utiliser signe de lateral_g
                lateral_g_in_corner = lateral_g[corner_indices]
                lateral_g_mean = np.mean(lateral_g_in_corner)
                corner_type = "left" if lateral_g_mean > 0 else "right"
            
            # APEX = point de |lateral_g| MAX
            lateral_g_abs_in_corner = np.abs([lateral_g[i] for i in corner_indices])
            apex_local_idx = np.argmax(lateral_g_abs_in_corner)
            apex_index = int(corner_indices[apex_local_idx])
            
            # Marquer colonnes
            for idx in corner_indices:
                if idx < len(df_result):
                    df_result.at[df_result.index[idx], 'is_corner'] = True
                    df_result.at[df_result.index[idx], 'corner_id'] = corner_id
                    df_result.at[df_result.index[idx], 'corner_type'] = corner_type
            
            if apex_index < len(df_result):
                df_result.at[df_result.index[apex_index], 'is_apex'] = True
            
            # Extraire métadonnées
            max_lateral_g = float(np.max(np.abs([lateral_g[i] for i in corner_indices])))
            distance_m = float(cumulative_dist[end_idx] - cumulative_dist[start_idx]) if end_idx < len(cumulative_dist) and start_idx < len(cumulative_dist) else 0.0
            duration_s = 0.0
            if time is not None and end_idx < len(time) and start_idx < len(time):
                if pd.notna(time[start_idx]) and pd.notna(time[end_idx]):
                    duration_s = float(time[end_idx] - time[start_idx])
            
            corner_detail = {
                'id': corner_id,
                'type': corner_type,
                'entry_index': int(start_idx),
                'apex_index': int(apex_index),
                'exit_index': int(end_idx),
                'entry_speed_kmh': float(speed[start_idx]) if start_idx < len(speed) and pd.notna(speed[start_idx]) else 0.0,
                'apex_speed_kmh': float(speed[apex_index]) if apex_index < len(speed) and pd.notna(speed[apex_index]) else 0.0,
                'exit_speed_kmh': float(speed[end_idx]) if end_idx < len(speed) and pd.notna(speed[end_idx]) else 0.0,
                'max_lateral_g': max_lateral_g,
                'distance_m': distance_m,
                'duration_s': duration_s
            }
            corner_details.append(corner_detail)
        
        # Métadonnées globales
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
        df_result.attrs['corners'] = {
            'total_corners': 0,
            'total_distance_m': 0.0,
            'avg_speed_kmh': 0.0,
            'max_lateral_g': 0.0,
            'corner_details': []
        }
    
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
