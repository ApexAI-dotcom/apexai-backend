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


def calculate_optimal_apex_speed(
    corner_data: pd.DataFrame,
    corner_type: str = "right"
) -> float:
    """
    Calcule la vitesse apex optimale théorique.
    
    Formule : V_opt = sqrt((R * g * μ * cos(θ)) / (1 - μ * sin(θ)))
    Simplifiée : V_opt = sqrt(R * g * μ) pour piste plate
    
    Args:
        corner_data: DataFrame avec points du virage
        corner_type: "left" ou "right"
    
    Returns:
        Vitesse optimale en km/h
    """
    try:
        if 'curvature' not in corner_data.columns:
            return 0.0
        
        curvature = pd.to_numeric(corner_data['curvature'], errors='coerce').fillna(0).values
        curvature_abs = np.abs(curvature[curvature != 0])
        
        if len(curvature_abs) == 0:
            return 0.0
        
        # Rayon moyen
        curvature_mean = np.mean(curvature_abs)
        if curvature_mean <= 0:
            return 0.0
        
        radius = 1.0 / curvature_mean  # Rayon en mètres
        
        # Vitesse optimale (piste plate, θ=0)
        g = KARTING_CONSTANTS['g']
        mu = KARTING_CONSTANTS['mu_tire']
        
        v_optimal_ms = np.sqrt(mu * g * radius)
        v_optimal_kmh = v_optimal_ms * 3.6
        
        # Validation : 30 < v_optimal < 150 km/h
        if 30.0 < v_optimal_kmh < 150.0:
            return float(v_optimal_kmh)
        else:
            return 0.0
    
    except Exception as e:
        warnings.warn(f"Error calculating optimal apex speed: {str(e)}")
        return 0.0


def calculate_braking_point(
    df: pd.DataFrame,
    corner_entry_idx: int,
    apex_idx: int,
    entry_speed: float,
    apex_speed: float
) -> Dict[str, float]:
    """
    Calcule le point de freinage optimal et réel.
    
    Args:
        df: DataFrame complet
        corner_entry_idx: Index du point d'entrée du virage
        apex_idx: Index de l'apex
        entry_speed: Vitesse à l'entrée (km/h)
        apex_speed: Vitesse à l'apex (km/h)
    
    Returns:
        Dictionnaire avec braking_point_real, braking_point_optimal, braking_delta
    """
    try:
        if 'cumulative_distance' not in df.columns:
            return {
                'braking_point_distance': 0.0,
                'braking_point_optimal': 0.0,
                'braking_delta': 0.0
            }
        
        dist = pd.to_numeric(df['cumulative_distance'], errors='coerce').values
        
        if apex_idx >= len(dist) or corner_entry_idx >= len(dist):
            return {
                'braking_point_distance': 0.0,
                'braking_point_optimal': 0.0,
                'braking_delta': 0.0
            }
        
        apex_dist = dist[apex_idx]
        entry_dist = dist[corner_entry_idx]
        
        # Détecter point de freinage réel (décélération > 0.5g)
        braking_idx = None
        if 'speed' in df.columns and corner_entry_idx < apex_idx:
            speed = pd.to_numeric(df['speed'], errors='coerce').values
            
            for i in range(corner_entry_idx, apex_idx):
                if i + 1 < len(speed):
                    delta_v = speed[i+1] - speed[i]
                    if delta_v < -2.0:  # Décélération significative (> 2 km/h)
                        braking_idx = i
                        break
        
        if braking_idx is not None and braking_idx < len(dist):
            braking_point_real = apex_dist - dist[braking_idx]
        else:
            # Estimation : point où vitesse commence à baisser
            braking_point_real = (apex_dist - entry_dist) * 0.6
        
        # Calculer point de freinage optimal
        # Distance nécessaire : d = (v_entry² - v_apex²) / (2 * a)
        v_entry_ms = entry_speed / 3.6
        v_apex_ms = apex_speed / 3.6
        decel = KARTING_CONSTANTS['max_braking_decel'] * KARTING_CONSTANTS['g']
        
        if decel > 0:
            braking_distance_optimal = (v_entry_ms ** 2 - v_apex_ms ** 2) / (2 * decel)
        else:
            braking_distance_optimal = braking_point_real
        
        braking_delta = braking_point_real - braking_distance_optimal  # Positif = trop tôt, négatif = trop tard
        
        return {
            'braking_point_distance': round(braking_point_real, 1),
            'braking_point_optimal': round(braking_distance_optimal, 1),
            'braking_delta': round(braking_delta, 1)
        }
    
    except Exception as e:
        warnings.warn(f"Error calculating braking point: {str(e)}")
        return {
            'braking_point_distance': 0.0,
            'braking_point_optimal': 0.0,
            'braking_delta': 0.0
        }


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
        if apex_idx >= len(df):
            return {
                'apex_distance_error': 0.0,
                'apex_direction_error': None
            }
        
        real_lat = df.iloc[apex_idx]['latitude_smooth']
        real_lon = df.iloc[apex_idx]['longitude_smooth']
        
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
        if 'corner_type' in df.iloc[apex_idx]:
            corner_type = df.iloc[apex_idx]['corner_type']
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
        
        # Vitesses
        apex_speed_real = corner_data.get('apex_speed_kmh', 0.0)
        entry_speed = corner_data.get('entry_speed_kmh', 0.0)
        exit_speed = corner_data.get('exit_speed_kmh', 0.0)
        
        # Vitesse optimale
        apex_speed_optimal = calculate_optimal_apex_speed(corner_df, corner_type)
        if apex_speed_optimal <= 0:
            # Fallback : utiliser valeur depuis corner_data si disponible
            apex_speed_optimal = corner_data.get('optimal_apex_speed_kmh', apex_speed_real * 1.1)
        
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
        
        # Point de freinage
        braking_data = calculate_braking_point(df, entry_idx, apex_idx, entry_speed, apex_speed_real)
        
        # Temps dans virage
        if 'time' in df.columns and entry_idx < len(df) and exit_idx < len(df):
            time_entry = pd.to_numeric(df.iloc[entry_idx]['time'], errors='coerce')
            time_exit = pd.to_numeric(df.iloc[exit_idx]['time'], errors='coerce')
            if pd.notna(time_entry) and pd.notna(time_exit):
                time_in_corner = float(time_exit - time_entry)
            else:
                time_in_corner = corner_data.get('duration_s', 0.0)
        else:
            time_in_corner = corner_data.get('duration_s', 0.0)
        
        # Temps perdu
        corner_distance = corner_data.get('distance_m', 0.0)
        time_lost = calculate_time_lost(
            df, corner_df, apex_speed_real, apex_speed_optimal, corner_distance
        )
        
        # Score et grade pour ce virage
        corner_score = (
            speed_efficiency * 0.4 +  # 40% vitesse
            (1 - min(apex_error['apex_distance_error'] / 5.0, 1.0)) * 30.0 +  # 30% précision
            (max_lateral_g / 3.0) * 20.0 +  # 20% G latéral
            (1 - min(time_lost / 1.0, 1.0)) * 10.0  # 10% temps perdu
        )
        
        if corner_score >= 85:
            grade = "A"
        elif corner_score >= 75:
            grade = "B"
        elif corner_score >= 65:
            grade = "C"
        else:
            grade = "D"
        
        return {
            'corner_id': corner_id,
            'corner_type': corner_type,
            'corner_number': corner_id,
            'apex_lat': corner_data.get('apex_lat'),
            'apex_lon': corner_data.get('apex_lon'),
            'metrics': {
                'apex_speed_real': round(apex_speed_real, 1),
                'apex_speed_optimal': round(apex_speed_optimal, 1),
                'speed_efficiency': round(speed_efficiency / 100.0, 3),  # Ratio 0-1
                'apex_distance_error': apex_error['apex_distance_error'],
                'apex_direction_error': apex_error['apex_direction_error'],
                'lateral_g_max': round(max_lateral_g, 2),
                'lateral_g_optimal': round(lateral_g_optimal, 2),
                'entry_speed': round(entry_speed, 1),
                'exit_speed': round(exit_speed, 1),
                'braking_point_distance': braking_data['braking_point_distance'],
                'braking_point_optimal': braking_data['braking_point_optimal'],
                'braking_delta': braking_data['braking_delta'],
                'time_in_corner': round(time_in_corner, 2),
                'time_lost': time_lost
            },
            'grade': grade,
            'score': round(corner_score, 1)
        }
    
    except Exception as e:
        warnings.warn(f"Error analyzing corner {corner_data.get('id')}: {str(e)}")
        return {
            'corner_id': corner_data.get('id', 0),
            'corner_type': corner_data.get('type', 'right'),
            'corner_number': corner_data.get('id', 0),
            'apex_lat': corner_data.get('apex_lat'),
            'apex_lon': corner_data.get('apex_lon'),
            'metrics': {},
            'grade': 'C',
            'score': 50
        }
