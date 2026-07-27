#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Performance Metrics Analysis
Analyse détaillée de performance par virage
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import warnings

from src.analysis.scoring import KARTING_CONSTANTS, calculate_optimal_apex_position
from src.analysis.geometry import _haversine_distance

# Largeur de piste karting de compétition (CIK-FIA : minimum 8 m). Sert de borne
# PHYSIQUE : une erreur d'apex ne peut pas dépasser la largeur de la piste.
# Au-delà, c'est un artefact de calcul, pas une info exploitable par le pilote.
TRACK_WIDTH_M = 8.0
MAX_APEX_ERROR_M = TRACK_WIDTH_M / 2.0

def _pos(df, label) -> Optional[int]:
    """Position entière d'un label d'index.

    `apex_index` / `entry_index` / `exit_index` sont des LABELS d'index
    (`df.index[...]`), pas des positions. Les confondre (df.iloc[label]) faisait
    lire un point pris ailleurs sur le circuit — d'où des « apex ratés de 50 m »
    physiquement impossibles sur une piste de 8 m de large.
    """
    if label is None:
        return None
    try:
        p = df.index.get_loc(label)
        if isinstance(p, slice):
            return int(p.start or 0)
        if hasattr(p, "__len__"):
            import numpy as _np
            nz = _np.flatnonzero(p)
            return int(nz[0]) if len(nz) else None
        return int(p)
    except Exception:
        return None


def _apex_speeds_per_lap(
    df: pd.DataFrame,
    corner_indices: List[int],
) -> List[float]:
    """
    Vitesse apex par tour = minimum de vitesse dans le segment pour chaque tour.
    (speed en km/h dans le pipeline.)
    
    Returns:
        Liste des vitesses apex en km/h, une par tour où le virage est présent.
    """
    if not corner_indices or 'speed' not in df.columns:
        return []
    try:
        valid_indices = [i for i in corner_indices if i in df.index]
        if not valid_indices:
            return []
        sub = df.loc[valid_indices].copy()
        if len(sub) == 0:
            return []
        lap_col = 'lap_number' if 'lap_number' in df.columns else None
        if not lap_col:
            return [round(float(sub['speed'].min()), 1)]
        lap_numbers = pd.to_numeric(sub[lap_col], errors='coerce').fillna(1).astype(int)
        sub = sub.assign(_lap=lap_numbers)
        unique_laps = sorted(sub['_lap'].unique())
        unique_laps = [lap for lap in unique_laps if lap >= 1]
        if not unique_laps:
            return [round(float(sub['speed'].min()), 1)]
        apex_speeds_per_lap = []
        for lap in unique_laps:
            lap_rows = sub[sub['_lap'] == lap]
            if len(lap_rows) > 0:
                min_speed = float(lap_rows['speed'].min())
                apex_speeds_per_lap.append(min_speed)
        return apex_speeds_per_lap
    except Exception as e:
        warnings.warn(f"Erreur _apex_speeds_per_lap: {e}")
        return []


def _entry_exit_speeds_from_gps(
    df: pd.DataFrame,
    apex_idx: int,
    n_points: int = 15,
    min_points: int = 5,
) -> tuple:
    """
    Calcule entry_speed (moyenne pondérée sur n_points avant l'apex) et
    exit_speed (moyenne pondérée sur n_points après l'apex).
    Plus de poids sur les points proches de l'apex.
    Returns (entry_speed_kmh, exit_speed_kmh) ou (None, None) si données insuffisantes.
    """
    if "speed" not in df.columns:
        return (None, None)
    try:
        pos_apex = df.index.get_loc(apex_idx)
    except (KeyError, TypeError):
        return (None, None)
    if isinstance(pos_apex, slice):
        pos_apex = pos_apex.start if pos_apex.start is not None else 0
    pos_apex = int(pos_apex)
    start = max(0, pos_apex - n_points)
    entry_slice = df.iloc[start:pos_apex]
    end = min(len(df), pos_apex + n_points + 1)
    exit_slice = df.iloc[pos_apex + 1 : end]
    if len(entry_slice) < min_points or len(exit_slice) < min_points:
        return (None, None)
    speed_col = pd.to_numeric(entry_slice["speed"], errors="coerce").fillna(0)
    if speed_col.isna().all() or (speed_col <= 0).all():
        entry_kmh = None
    else:
        weights_entry = np.arange(1, len(entry_slice) + 1, dtype=float)
        entry_kmh = round(float(np.average(speed_col.values, weights=weights_entry)), 1)
    speed_exit = pd.to_numeric(exit_slice["speed"], errors="coerce").fillna(0)
    if speed_exit.isna().all() or (speed_exit <= 0).all():
        exit_kmh = None
    else:
        weights_exit = np.arange(len(exit_slice), 0, -1, dtype=float)
        exit_kmh = round(float(np.average(speed_exit.values, weights=weights_exit)), 1)
    return (entry_kmh, exit_kmh)


def calculate_optimal_apex_speed_from_laps(
    df: pd.DataFrame,
    corner_indices: List[int],
) -> float:
    """
    Vitesse optimale à l'apex calculée physiquement avec V_opt = sqrt(R_opt * g * mu)
    
    Returns:
        Vitesse max en km/h, ou 0.0 si pas de données
    """
    from src.analysis.scoring import KARTING_CONSTANTS
    
    try:
        if not corner_indices or 'curvature' not in df.columns:
            return 0.0
            
        valid_indices = [i for i in corner_indices if i in df.index]
        if not valid_indices:
            return 0.0
            
        curvature_vals = pd.to_numeric(df.loc[valid_indices, 'curvature'], errors='coerce').abs()
        curvature_valid = curvature_vals[~curvature_vals.isna()]
        
        if len(curvature_valid) == 0:
            return 0.0
            
        # Rayon moyen sur le virage
        curvature_mean = float(curvature_valid.mean())
        if curvature_mean <= 0.0001:
            return 0.0 # Ligne droite
            
        radius = 1.0 / curvature_mean
        
        # V_opt = sqrt(R * g * mu)
        mu = 1.1 # Grip coefficient for slicks
        v_opt_ms = np.sqrt(radius * KARTING_CONSTANTS['g'] * mu)
        
        v_opt_kmh = v_opt_ms * 3.6
        
        # Clamp pour éviter des valeurs folles sur de faux rayons (ex: très grands rayons GPS)
        v_opt_kmh = max(30.0, min(140.0, v_opt_kmh))
        
        return round(float(v_opt_kmh), 1)
        
    except Exception as e:
        warnings.warn(f"Erreur calculate_optimal_apex_speed_from_laps: {e}")
        return 0.0


def calculate_braking_point(
    df: pd.DataFrame,
    corner_entry_idx: int,
    apex_idx: int,
    entry_speed: float,
    apex_speed: float,
    corner_id: Optional[int] = None,
) -> Dict[str, float]:
    """
    Repère de freinage d'un virage.

    Ne calcule plus rien : lit le résultat de `src.analysis.braking`, qui est la
    source unique. La carte, les chiffres et les conseils y puisent tous, si
    bien qu'aucun affichage ne peut en contredire un autre.

    Un virage pris à plat ne renvoie pas de repère plutôt qu'un repère faux.
    """
    empty = {
        'braking_point_distance': 0.0,
        'braking_point_optimal': 0.0,
        'braking_delta': 0.0,
        'braking_lat': None,
        'braking_lon': None,
    }
    if corner_id is None:
        return empty
    try:
        from src.analysis.braking import get_braking_analysis
        info = get_braking_analysis(df).get("by_corner", {}).get(int(corner_id))
        if not info:
            return empty
        return {
            'braking_point_distance': info.get('braking_point_distance', 0.0),
            'braking_point_optimal': info.get('braking_point_optimal', 0.0),
            'braking_delta': info.get('braking_delta', 0.0),
            'braking_lat': info.get('braking_lat'),
            'braking_lon': info.get('braking_lon'),
        }
    except Exception as e:
        warnings.warn(f"calculate_braking_point: {e}")
        return empty


def calculate_apex_error(
    df: pd.DataFrame,
    apex_idx: int,
    corner_indices: List[int]
) -> Dict[str, Any]:
    """
    Calcule l'erreur de position de l'apex.
    
    Args:
        df: DataFrame complet
        apex_idx: Index de l'apex réel
        corner_indices: Liste des indices du virage
    
    Returns:
        Dictionnaire avec distance_error, direction_error
    """
    try:
        if apex_idx is None or apex_idx not in df.index:
            return {
                'apex_distance_error': 0.0,
                'apex_direction_error': None
            }

        apex_row = df.loc[apex_idx]
        if hasattr(apex_row, "iloc") and getattr(apex_row, "ndim", 1) > 1:
            apex_row = apex_row.iloc[0]
        real_lat = apex_row['latitude_smooth']
        real_lon = apex_row['longitude_smooth']
        
        if pd.isna(real_lat) or pd.isna(real_lon):
            return {
                'apex_distance_error': 0.0,
                'apex_direction_error': None
            }
        
        # Apex idéal
        optimal_apex = calculate_optimal_apex_position(df, corner_indices)
        
        if optimal_apex is None:
            return {
                'apex_distance_error': 0.0,
                'apex_direction_error': None
            }
        
        # Distance
        distance_error = _haversine_distance(
            float(real_lat), float(real_lon),
            optimal_apex['latitude'], optimal_apex['longitude']
        )
        
        # Direction de l'erreur
        # Calculer bearing de l'apex réel vers l'idéal
        dlat = optimal_apex['latitude'] - float(real_lat)
        dlon = optimal_apex['longitude'] - float(real_lon)
        
        if abs(dlat) > abs(dlon):
            if dlat > 0:
                direction = "north"  # Trop au sud
            else:
                direction = "south"  # Trop au nord
        else:
            if dlon > 0:
                direction = "east"  # Trop à l'ouest
            else:
                direction = "west"  # Trop à l'est
        
        # Simplifier en left/right si possible
        if 'corner_type' in apex_row:
            corner_type = apex_row['corner_type']
            if corner_type == "right":
                if dlon > 0:
                    direction = "right"  # Trop à droite
                else:
                    direction = "left"  # Trop à gauche
            elif corner_type == "left":
                if dlon > 0:
                    direction = "left"  # Trop à gauche
                else:
                    direction = "right"  # Trop à droite
        
        # Garde-fou physique : sur une piste de 8 m, un apex ne peut pas être
        # raté de plus d'une demi-largeur. Au-delà, la mesure n'est pas fiable
        # (apex de référence mal apparié) : on ne l'affiche pas plutôt que
        # d'annoncer au pilote une erreur impossible.
        if distance_error > MAX_APEX_ERROR_M:
            return {
                'apex_distance_error': 0.0,
                'apex_direction_error': None,
                'apex_error_unreliable': True,
            }

        return {
            'apex_distance_error': round(distance_error, 2),
            'apex_direction_error': direction
        }
    
    except Exception as e:
        warnings.warn(f"Error calculating apex error: {str(e)}")
        return {
            'apex_distance_error': 0.0,
            'apex_direction_error': None
        }


def calculate_time_lost(
    df: pd.DataFrame,
    corner_data: pd.DataFrame,
    apex_speed_real: float,
    apex_speed_optimal: float,
    corner_distance: float
) -> float:
    """
    Calcule le temps perdu dans un virage vs optimal.
    
    Approximation : temps perdu ≈ distance * (1/v_real - 1/v_optimal)
    
    Args:
        df: DataFrame complet
        corner_data: Points du virage
        apex_speed_real: Vitesse apex réelle (km/h)
        apex_speed_optimal: Vitesse apex optimale (km/h)
        corner_distance: Distance du virage (m)
    
    Returns:
        Temps perdu en secondes
    """
    try:
        if apex_speed_real <= 0 or apex_speed_optimal <= 0:
            return 0.0
        
        # Vitesse moyenne dans le virage (approximation)
        if 'speed' in corner_data.columns:
            avg_speed = pd.to_numeric(corner_data['speed'], errors='coerce').mean()
            avg_speed = avg_speed if not pd.isna(avg_speed) else apex_speed_real
        else:
            avg_speed = apex_speed_real
        
        # Vitesse moyenne optimale
        avg_speed_optimal = avg_speed * (apex_speed_optimal / apex_speed_real) if apex_speed_real > 0 else avg_speed
        
        # Temps réel vs optimal
        if avg_speed > 0:
            time_real = (corner_distance / 1000) / (avg_speed / 3600)  # heures -> secondes
        else:
            time_real = 0
        
        if avg_speed_optimal > 0:
            time_optimal = (corner_distance / 1000) / (avg_speed_optimal / 3600)
        else:
            time_optimal = time_real
        
        time_lost = max(0, time_real - time_optimal)
        
        return round(time_lost, 2)
    
    except Exception as e:
        warnings.warn(f"Error calculating time lost: {str(e)}")
        return 0.0


def analyze_corner_performance(
    df: pd.DataFrame,
    corner_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyse détaillée de performance pour un virage.
    
    Args:
        df: DataFrame complet avec toutes les colonnes
        corner_data: Dictionnaire avec détails du virage (depuis df.attrs['corners']['corner_details'])
    
    Returns:
        Dictionnaire avec toutes les métriques de performance
    """
    try:
        corner_id = corner_data.get('id')
        apex_idx = corner_data.get('apex_index')
        entry_idx = corner_data.get('entry_index')
        exit_idx = corner_data.get('exit_index')
        corner_type = corner_data.get('type', 'right')
        
        if apex_idx is None or entry_idx is None or exit_idx is None:
            return {
                'corner_id': corner_id,
                'corner_type': corner_type,
                'corner_number': corner_id,
                'metrics': {},
                'grade': 'C',
                'score': 50
            }
        
        # Extraire données du virage
        corner_mask = df['corner_id'] == corner_id
        corner_df = df[corner_mask].copy()
        corner_indices = corner_df.index.tolist()
        
        if len(corner_indices) < 3:
            return {
                'corner_id': corner_id,
                'corner_type': corner_type,
                'corner_number': corner_id,
                'metrics': {},
                'grade': 'C',
                'score': 50
            }
        
        # Vitesses entry/exit = moyennes pondérées sur 15 points GPS avant/après apex
        entry_speed_raw, exit_speed_raw = _entry_exit_speeds_from_gps(df, apex_idx)
        entry_speed = float(entry_speed_raw) if entry_speed_raw is not None else corner_data.get('entry_speed_kmh', 0.0) or 0.0
        exit_speed = float(exit_speed_raw) if exit_speed_raw is not None else corner_data.get('exit_speed_kmh', 0.0) or 0.0
        apex_speeds_per_lap = _apex_speeds_per_lap(df, corner_indices)
        if apex_speeds_per_lap:
            apex_speed_real = round(float(np.mean(apex_speeds_per_lap)), 1)
            apex_speed_optimal = round(max(apex_speeds_per_lap), 1)
            apex_speed_optimal = max(apex_speed_optimal, apex_speed_real)
        else:
            apex_speed_real = corner_data.get('apex_speed_kmh', 0.0)
            apex_speed_optimal = calculate_optimal_apex_speed_from_laps(df, corner_indices)
            if apex_speed_optimal <= 0 and 'speed' in corner_df.columns and len(corner_df) > 0:
                apex_speed_optimal = round(float(corner_df['speed'].min()), 1)
            if apex_speed_optimal <= 0:
                apex_speed_optimal = apex_speed_real
            apex_speed_optimal = max(apex_speed_optimal, apex_speed_real)
        speed_efficiency = (apex_speed_real / apex_speed_optimal * 100) if apex_speed_optimal > 0 else 80.0
        
        # Erreur apex
        apex_error = calculate_apex_error(df, apex_idx, corner_indices)
        
        # G latéral
        max_lateral_g = corner_data.get('max_lateral_g', 0.0)
        
        # G latéral optimal (théorique)
        if apex_speed_optimal > 0 and 'curvature' in corner_df.columns:
            curvature_mean = pd.to_numeric(corner_df['curvature'], errors='coerce').abs().mean()
            if curvature_mean > 0:
                radius = 1.0 / curvature_mean
                v_opt_ms = apex_speed_optimal / 3.6
                lateral_g_optimal = (v_opt_ms ** 2) / (radius * KARTING_CONSTANTS['g'])
            else:
                lateral_g_optimal = max_lateral_g
        else:
            lateral_g_optimal = max_lateral_g
        
        # Point de freinage — lu dans l'analyse de freinage, jamais recalculé.
        # Deux calculs indépendants du même repère finissent toujours par
        # diverger ; c'est ce qui faisait apparaître une pastille ailleurs que
        # sa bande sur la carte.
        braking_data = calculate_braking_point(df, entry_idx, apex_idx, entry_speed,
                                               apex_speed_real, corner_id=corner_id)
        
        # Temps dans virage (entry_idx / exit_idx sont des LABELS)
        if 'time' in df.columns and entry_idx in df.index and exit_idx in df.index:
            time_entry = pd.to_numeric(df.loc[entry_idx, 'time'], errors='coerce')
            time_exit = pd.to_numeric(df.loc[exit_idx, 'time'], errors='coerce')
            if hasattr(time_entry, "iloc"):
                time_entry = time_entry.iloc[0]
            if hasattr(time_exit, "iloc"):
                time_exit = time_exit.iloc[0]
            if pd.notna(time_entry) and pd.notna(time_exit):
                time_in_corner = float(time_exit - time_entry)
            else:
                time_in_corner = corner_data.get('duration_s', 0.0)
        else:
            time_in_corner = corner_data.get('duration_s', 0.0)
        
        # Temps perdu = différence entre tour moyen et meilleur tour à ce virage
        corner_distance = corner_data.get('distance_m', 0.0)
        if corner_indices and 'cumulative_distance' in df.columns:
            valid_idx = [i for i in corner_indices if i in df.index]
            if valid_idx:
                dist_vals = df.loc[valid_idx, 'cumulative_distance']
                segment_length = abs(float(dist_vals.max()) - float(dist_vals.min()))
                if segment_length > 5000:
                    segment_length = segment_length / 1000.0  # mm → m
                if segment_length > 500:
                    segment_length = segment_length / 100.0  # cm → m
                segment_length = max(5.0, min(200.0, segment_length))
            else:
                segment_length = corner_distance if corner_distance > 0 else 30.0
        else:
            segment_length = corner_distance if corner_distance > 0 else 30.0
        v_real_ms = apex_speed_real / 3.6
        v_opt_ms = apex_speed_optimal / 3.6
        if v_real_ms > 0 and v_opt_ms > 0 and v_opt_ms > v_real_ms:
            time_lost = segment_length / v_real_ms - segment_length / v_opt_ms
            time_lost = round(max(0.0, min(time_lost, 5.0)), 3)
        else:
            time_lost = 0.0
        
        # Score et grade pour ce virage
        corner_score = (
            speed_efficiency * 0.4 +  # 40% vitesse
            (1 - min(apex_error['apex_distance_error'] / 5.0, 1.0)) * 30.0 +  # 30% précision
            (max_lateral_g / 3.0) * 20.0 +  # 20% G latéral
            (1 - min(time_lost / 1.0, 1.0)) * 10.0  # 10% temps perdu
        )
        
        if corner_score >= 80:
            grade = "A"
        elif corner_score >= 68:
            grade = "B"
        elif corner_score >= 52:
            grade = "C"
        elif corner_score >= 38:
            grade = "D"
        else:
            grade = "F"
        
        # Cibles : +3% entrée, sortie = vitesse apex optimale (affichées seulement si entry/exit calculés)
        has_entry_exit = (entry_speed_raw is not None and exit_speed_raw is not None)
        target_entry_speed = round(entry_speed * 1.03, 1) if entry_speed and has_entry_exit else None
        target_exit_speed = round(apex_speed_optimal, 1) if has_entry_exit else None
        metrics_out = {
            'apex_speed_real': round(apex_speed_real, 1),
            'apex_speed_optimal': round(apex_speed_optimal, 1),
            'speed_efficiency': round(speed_efficiency / 100.0, 3),
            'apex_distance_error': apex_error['apex_distance_error'],
            'apex_direction_error': apex_error['apex_direction_error'],
            'lateral_g_max': round(max_lateral_g, 2),
            'lateral_g_optimal': round(lateral_g_optimal, 2),
            'entry_speed': round(entry_speed, 1) if entry_speed else None,
            'exit_speed': round(exit_speed, 1) if exit_speed else None,
            'target_entry_speed': target_entry_speed,
            'target_exit_speed': target_exit_speed,
            'braking_point_distance': braking_data['braking_point_distance'],
            'braking_point_optimal': braking_data['braking_point_optimal'],
            'braking_delta': braking_data['braking_delta'],
            'braking_lat': braking_data.get('braking_lat'),
            'braking_lon': braking_data.get('braking_lon'),
            'time_in_corner': round(time_in_corner, 2),
            'time_lost': time_lost
        }
        return {
            'corner_id': corner_id,
            'corner_type': corner_type,
            'corner_number': corner_id,
            'apex_lat': corner_data.get('apex_lat'),
            'apex_lon': corner_data.get('apex_lon'),
            'metrics': metrics_out,
            'grade': grade,
            'score': round(corner_score, 1)
        }
    
    except Exception as e:
        warnings.warn(f"Error analyzing corner {corner_data.get('id')}: {str(e)}")
        # Tenter de récupérer au moins la vitesse réelle si elle existe
        fallback_real = corner_data.get('apex_speed', 0.0)
        return {
            'corner_id': corner_data.get('id', 0),
            'corner_type': corner_data.get('type', 'right'),
            'corner_number': corner_data.get('id', 0),
            'apex_lat': corner_data.get('apex_lat'),
            'apex_lon': corner_data.get('apex_lon'),
            'metrics': {
                'apex_speed_real': round(fallback_real, 1) if fallback_real else 0.0,
                'apex_speed_optimal': round(fallback_real, 1) if fallback_real else 0.0, # Évite un gros delta
                'time_lost': 0.0
            },
            'grade': 'C',
            'score': 50
        }
