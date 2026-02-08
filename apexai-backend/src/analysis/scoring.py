#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Performance Scoring System
Système de notation /100 pour évaluer la performance de pilotage
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import warnings

from src.analysis.geometry import _haversine_distance

# CONSTANTES PHYSIQUES
KARTING_CONSTANTS = {
    "mu_tire": 1.3,  # Coefficient adhérence pneu karting
    "g": 9.81,  # m/s²
    "max_lateral_g": 3.0,  # g (limite sécurité)
    "max_braking_decel": 1.5,  # g
    "corner_weight_speed": 0.7,  # Poids des virages rapides (>60km/h)
    "corner_weight_slow": 0.3,  # Poids des virages lents
    "optimal_consistency_threshold": 0.15,  # Écart-type acceptable
}


def calculate_optimal_apex_position(
    df: pd.DataFrame,
    corner_indices: List[int]
) -> Optional[Dict[str, float]]:
    """
    Calcule la position de l'apex idéal pour un virage.
    
    Args:
        df: DataFrame avec colonnes GPS et géométrie
        corner_indices: Liste des indices des points du virage
    
    Returns:
        Dictionnaire avec lat/lon de l'apex idéal, ou None si erreur
    """
    try:
        if not corner_indices or len(corner_indices) < 3:
            return None
        
        # Extraire données du virage
        corner_data = df.iloc[corner_indices].copy()
        
        if 'curvature' not in corner_data.columns:
            return None
        
        curvature = pd.to_numeric(corner_data['curvature'], errors='coerce').values
        curvature_abs = np.abs(curvature)
        
        # Apex idéal = point où courbure maximale (rayon minimal)
        if np.all(np.isnan(curvature_abs)):
            return None
        
        max_curvature_idx = np.nanargmax(curvature_abs)
        ideal_idx = corner_indices[max_curvature_idx]
        
        if ideal_idx >= len(df):
            return None
        
        apex_lat = df.iloc[ideal_idx]['latitude_smooth']
        apex_lon = df.iloc[ideal_idx]['longitude_smooth']
        
        if pd.isna(apex_lat) or pd.isna(apex_lon):
            return None
        
        return {
            'latitude': float(apex_lat),
            'longitude': float(apex_lon),
            'index': int(ideal_idx)
        }
    
    except Exception as e:
        warnings.warn(f"Error calculating optimal apex: {str(e)}")
        return None


def calculate_apex_precision_score(
    df: pd.DataFrame,
    corner_details: List[Dict[str, Any]]
) -> float:
    """
    Calcule le score de précision des apex (0-30 points).
    
    Args:
        df: DataFrame avec colonnes GPS et is_apex
        corner_details: Liste des détails de chaque virage
    
    Returns:
        Score entre 0 et 30
    """
    if not corner_details:
        return 15.0  # Score par défaut si pas de virages
    
    distances = []
    
    for corner in corner_details:
        try:
            apex_idx = corner.get('apex_index')
            if apex_idx is None or apex_idx >= len(df):
                continue
            
            # Apex réel
            real_lat = df.iloc[apex_idx]['latitude_smooth']
            real_lon = df.iloc[apex_idx]['longitude_smooth']
            
            if pd.isna(real_lat) or pd.isna(real_lon):
                continue
            
            # Trouver les indices du virage pour calculer l'apex idéal
            corner_mask = df['corner_id'] == corner['id']
            corner_indices = df[corner_mask].index.tolist()
            
            if len(corner_indices) < 3:
                continue
            
            # Apex idéal
            optimal_apex = calculate_optimal_apex_position(df, corner_indices)
            
            if optimal_apex is None:
                continue
            
            # Distance Haversine
            dist = _haversine_distance(
                float(real_lat), float(real_lon),
                optimal_apex['latitude'], optimal_apex['longitude']
            )
            
            if dist > 0:
                distances.append(dist)
        
        except Exception as e:
            warnings.warn(f"Error calculating apex precision for corner {corner.get('id')}: {str(e)}")
            continue
    
    if not distances:
        return 15.0  # Score moyen par défaut
    
    avg_distance = np.mean(distances)
    
    # Score basé sur moyenne des écarts
    # 0-0.5m = 30 pts, 0.5-1.5m = 25 pts, 1.5-3m = 20 pts, 3-5m = 15 pts, >5m = 5-10 pts
    if avg_distance <= 0.5:
        score = 30.0
    elif avg_distance <= 1.5:
        score = 25.0
    elif avg_distance <= 3.0:
        score = 20.0
    elif avg_distance <= 5.0:
        score = 15.0
    else:
        score = max(5.0, 10.0 * (1 - (avg_distance - 5.0) / 10.0))
    
    # Formule alternative pour continuité
    score_continuous = 30.0 * (1 - min(avg_distance / 5.0, 1.0))
    
    return max(score, score_continuous)


def calculate_trajectory_consistency_score(df: pd.DataFrame) -> float:
    """
    Calcule le score de régularité de trajectoire (0-20 points).
    
    Args:
        df: DataFrame avec colonnes curvature, heading
    
    Returns:
        Score entre 0 et 20
    """
    try:
        if 'curvature' not in df.columns:
            return 10.0  # Score moyen par défaut
        
        curvature = pd.to_numeric(df['curvature'], errors='coerce').fillna(0).values
        
        # Écart-type de la courbure
        curvature_std = np.std(np.abs(curvature))
        
        # Détecter micro-corrections (variations brutales du heading)
        if 'heading' in df.columns:
            heading = pd.to_numeric(df['heading'], errors='coerce').fillna(0).values
            
            # Calculer variations de heading
            heading_diff = np.diff(heading)
            # Normaliser dans [-180, 180]
            heading_diff = np.where(heading_diff > 180, heading_diff - 360, heading_diff)
            heading_diff = np.where(heading_diff < -180, heading_diff + 360, heading_diff)
            
            # Détecter corrections > 5° en 0.5s (approximation: 10 points si 10Hz)
            corrections = np.sum(np.abs(heading_diff) > 5.0)
            correction_ratio = corrections / len(heading_diff) if len(heading_diff) > 0 else 0
        else:
            correction_ratio = 0
        
        # Score basé sur écart-type et corrections
        # std_deviation faible + peu de corrections = score élevé
        consistency_from_std = 20.0 * (1 - min(curvature_std / 0.3, 1.0))
        consistency_from_corrections = 20.0 * (1 - min(correction_ratio * 10, 1.0))
        
        # Moyenne pondérée
        score = (consistency_from_std * 0.6 + consistency_from_corrections * 0.4)
        
        return max(0.0, min(20.0, score))
    
    except Exception as e:
        warnings.warn(f"Error calculating trajectory consistency: {str(e)}")
        return 10.0


def calculate_apex_speed_score(corner_details: List[Dict[str, Any]]) -> float:
    """
    Calcule le score de vitesse aux apex (0-25 points).
    
    Args:
        corner_details: Liste des détails de chaque virage avec speed_efficiency_pct
    
    Returns:
        Score entre 0 et 25
    """
    if not corner_details:
        return 12.5  # Score moyen par défaut
    
    efficiencies = []
    weights = []
    
    for corner in corner_details:
        try:
            efficiency = corner.get('speed_efficiency_pct', 80.0)
            apex_speed = corner.get('apex_speed_kmh', 0.0)
            
            if apex_speed <= 0:
                continue
            
            # Poids selon vitesse (virages rapides = plus de poids)
            if apex_speed > 60:
                weight = KARTING_CONSTANTS['corner_weight_speed']
            else:
                weight = KARTING_CONSTANTS['corner_weight_slow']
            
            efficiencies.append(efficiency)
            weights.append(weight)
        
        except Exception:
            continue
    
    if not efficiencies:
        return 12.5
    
    # Moyenne pondérée
    weights = np.array(weights)
    weights = weights / np.sum(weights)  # Normaliser
    
    avg_efficiency = np.average(efficiencies, weights=weights)
    
    # Score par efficacité
    if avg_efficiency >= 90:
        score = 25.0
    elif avg_efficiency >= 80:
        score = 20.0
    elif avg_efficiency >= 70:
        score = 15.0
    else:
        score = max(5.0, 10.0 * (avg_efficiency / 70))
    
    return score


def calculate_sector_times_score(
    df: pd.DataFrame,
    corner_details: List[Dict[str, Any]]
) -> float:
    """
    Calcule le score des temps secteurs (0-25 points).
    
    Args:
        df: DataFrame avec colonnes cumulative_distance et time
        corner_details: Liste des détails de chaque virage
    
    Returns:
        Score entre 0 et 25
    """
    try:
        if 'cumulative_distance' not in df.columns or 'time' not in df.columns:
            return 12.5  # Score moyen par défaut
        
        dist = pd.to_numeric(df['cumulative_distance'], errors='coerce').values
        time = pd.to_numeric(df['time'], errors='coerce').values
        
        if len(dist) == 0 or len(time) == 0:
            return 12.5
        
        total_dist = dist[-1] if not pd.isna(dist[-1]) else 0
        total_time = time[-1] - time[0] if len(time) > 1 and not pd.isna(time[-1]) and not pd.isna(time[0]) else 0
        
        if total_dist == 0 or total_time == 0:
            return 12.5
        
        # Diviser en 3 secteurs
        s1_end = total_dist / 3
        s2_end = 2 * total_dist / 3
        
        s1_idx = np.argmin(np.abs(dist - s1_end))
        s2_idx = np.argmin(np.abs(dist - s2_end))
        
        # Calculer temps secteurs
        s1_time = time[s1_idx] - time[0] if s1_idx < len(time) else 0
        s2_time = time[s2_idx] - time[s1_idx] if s2_idx < len(time) and s1_idx < len(time) else 0
        s3_time = time[-1] - time[s2_idx] if s2_idx < len(time) else 0
        
        # Calculer temps théorique optimal (approximation basée sur vitesse moyenne théorique)
        # Vitesse théorique = 70% de vitesse max si tout était optimal
        max_speed = df['speed'].max() if 'speed' in df.columns else 100.0
        theoretical_speed = max_speed * 0.7  # 70% de la vitesse max théorique
        
        theoretical_s1 = (s1_end / theoretical_speed) * 3.6  # Conversion m/s -> s
        theoretical_s2 = ((s2_end - s1_end) / theoretical_speed) * 3.6
        theoretical_s3 = ((total_dist - s2_end) / theoretical_speed) * 3.6
        
        # Ratio temps réel / temps théorique
        if theoretical_s1 > 0:
            ratio_s1 = min(1.0, theoretical_s1 / s1_time) if s1_time > 0 else 0.8
        else:
            ratio_s1 = 0.8
        
        if theoretical_s2 > 0:
            ratio_s2 = min(1.0, theoretical_s2 / s2_time) if s2_time > 0 else 0.8
        else:
            ratio_s2 = 0.8
        
        if theoretical_s3 > 0:
            ratio_s3 = min(1.0, theoretical_s3 / s3_time) if s3_time > 0 else 0.8
        else:
            ratio_s3 = 0.8
        
        avg_ratio = (ratio_s1 + ratio_s2 + ratio_s3) / 3.0
        
        # Score basé sur ratio
        if avg_ratio >= 1.0:
            score = 25.0
        elif avg_ratio >= 0.95:
            score = 22.0
        elif avg_ratio >= 0.90:
            score = 18.0
        elif avg_ratio >= 0.85:
            score = 12.0
        else:
            score = max(5.0, 5.0 * (avg_ratio / 0.85))
        
        return score
    
    except Exception as e:
        warnings.warn(f"Error calculating sector times score: {str(e)}")
        return 12.5


def calculate_performance_score(
    df: pd.DataFrame,
    corner_details: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calcule le score de performance global /100.
    
    Args:
        df: DataFrame avec toutes les colonnes de géométrie
        corner_details: Liste des détails de chaque virage depuis df.attrs['corners']
    
    Returns:
        Dictionnaire avec score global, breakdown, grade, percentile, détails
    """
    try:
        # 1. Précision Apex (30 points)
        apex_precision = calculate_apex_precision_score(df, corner_details)
        
        # 2. Régularité Trajectoire (20 points)
        trajectory_consistency = calculate_trajectory_consistency_score(df)
        
        # 3. Vitesse Apex (25 points)
        apex_speed = calculate_apex_speed_score(corner_details)
        
        # 4. Temps Secteur (25 points)
        sector_times = calculate_sector_times_score(df, corner_details)
        
        # Score global
        overall_score = apex_precision + trajectory_consistency + apex_speed + sector_times
        
        # Grade
        if overall_score >= 95:
            grade = "A+"
        elif overall_score >= 85:
            grade = "A"
        elif overall_score >= 75:
            grade = "B"
        elif overall_score >= 65:
            grade = "C"
        else:
            grade = "D"
        
        # Percentile (simulé, à remplacer par vraie DB si disponible)
        percentile = int(min(99, max(10, 10 + (overall_score - 50) * 1.5)))
        
        # Détails supplémentaires
        # Meilleurs et pires virages (basé sur efficacité vitesse)
        corner_scores = []
        for corner in corner_details:
            efficiency = corner.get('speed_efficiency_pct', 80.0)
            max_g = corner.get('max_lateral_g', 0.0)
            # Score simplifié pour chaque virage
            corner_score = efficiency * 0.7 + (max_g / 3.0) * 30.0
            corner_scores.append((corner['id'], corner_score))
        
        corner_scores.sort(key=lambda x: x[1], reverse=True)
        best_corners = [c[0] for c in corner_scores[:3]] if corner_scores else []
        worst_corners = [c[0] for c in corner_scores[-3:]] if corner_scores else []
        
        # Distance moyenne apex
        avg_apex_distance = 0.0
        distances_count = 0
        for corner in corner_details:
            try:
                apex_idx = corner.get('apex_index')
                if apex_idx is None or apex_idx >= len(df):
                    continue
                
                real_lat = df.iloc[apex_idx]['latitude_smooth']
                real_lon = df.iloc[apex_idx]['longitude_smooth']
                
                if pd.isna(real_lat) or pd.isna(real_lon):
                    continue
                
                corner_mask = df['corner_id'] == corner['id']
                corner_indices = df[corner_mask].index.tolist()
                
                if len(corner_indices) < 3:
                    continue
                
                optimal_apex = calculate_optimal_apex_position(df, corner_indices)
                if optimal_apex:
                    dist = _haversine_distance(
                        float(real_lat), float(real_lon),
                        optimal_apex['latitude'], optimal_apex['longitude']
                    )
                    avg_apex_distance += dist
                    distances_count += 1
            except Exception:
                continue
        
        if distances_count > 0:
            avg_apex_distance = avg_apex_distance / distances_count
        
        # Efficacité vitesse moyenne
        efficiencies = [c.get('speed_efficiency_pct', 80.0) for c in corner_details if 'speed_efficiency_pct' in c]
        avg_efficiency = np.mean(efficiencies) / 100.0 if efficiencies else 0.8
        
        # Index de constance
        if 'curvature' in df.columns:
            curvature = pd.to_numeric(df['curvature'], errors='coerce').fillna(0).values
            consistency_index = 1.0 - min(1.0, np.std(np.abs(curvature)) / 0.3)
        else:
            consistency_index = 0.75
        
        return {
            "overall_score": round(overall_score, 1),
            "breakdown": {
                "apex_precision": round(apex_precision, 1),
                "trajectory_consistency": round(trajectory_consistency, 1),
                "apex_speed": round(apex_speed, 1),
                "sector_times": round(sector_times, 1)
            },
            "grade": grade,
            "percentile": percentile,
            "details": {
                "best_corners": best_corners,
                "worst_corners": worst_corners,
                "avg_apex_distance": round(avg_apex_distance, 2),
                "avg_apex_speed_efficiency": round(avg_efficiency, 2),
                "consistency_index": round(consistency_index, 2)
            }
        }
    
    except Exception as e:
        warnings.warn(f"Error calculating performance score: {str(e)}")
        return {
            "overall_score": 60.0,
            "breakdown": {
                "apex_precision": 15.0,
                "trajectory_consistency": 10.0,
                "apex_speed": 12.5,
                "sector_times": 12.5
            },
            "grade": "C",
            "percentile": 50,
            "details": {
                "best_corners": [],
                "worst_corners": [],
                "avg_apex_distance": 0.0,
                "avg_apex_speed_efficiency": 0.8,
                "consistency_index": 0.75
            }
        }
