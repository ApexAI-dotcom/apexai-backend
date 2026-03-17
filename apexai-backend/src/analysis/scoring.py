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
    Calcule la position de l'apex idéal (point de courbure maximale) pour un virage.
    """
    try:
        if not corner_indices or len(corner_indices) < 3:
            return None
        
        valid_indices = [idx for idx in corner_indices if idx in df.index]
        if not valid_indices:
            return None
            
        corner_data = df.loc[valid_indices]
        
        # Le meilleur apex mathématique est là où on tourne le plus fort 
        # (ie: abs(curvature) au max)
        if 'curvature' not in corner_data.columns:
            # Fallback sur le G latéral si pss de courbure
            if 'lateral_g' in corner_data.columns:
                signal = pd.to_numeric(corner_data['lateral_g'], errors='coerce').abs()
            else:
                return None
        else:
            signal = pd.to_numeric(corner_data['curvature'], errors='coerce').abs()
            
        if np.all(np.isnan(signal)):
            return None
        
        max_idx_loc = np.nanargmax(signal.values)
        ideal_idx = valid_indices[max_idx_loc]
        
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
    Calcule le score de précision des apex (0-30 points) en mesurant le clustering 
    spatial des apex du pilote sur plusieurs tours (sa propre constance de trajectoire).
    
    Args:
        df: DataFrame global
        corner_details: Liste des détails de chaque virage (avec per_lap_data)
    
    Returns:
        Score entre 0 et 30
    """
    if not corner_details:
        return 20.0  # Par défaut bon score si aucun virage
    
    cluster_scores = []
    
    for corner in corner_details:
        try:
            per_lap = corner.get('per_lap_data', [])
            
            # Si un seul tour sélectionné, on n'a pas de baseline de variance,
            # on donne un très bon score par défaut pour ne pas pénaliser un one-shot.
            if len(per_lap) <= 1:
                cluster_scores.append(25.0)
                continue
                
            lats = []
            lons = []
            for pl in per_lap:
                a_idx = pl.get('apex_index')
                if a_idx is not None and a_idx in df.index:
                    lat = df.at[a_idx, 'latitude_smooth']
                    lon = df.at[a_idx, 'longitude_smooth']
                    if pd.notna(lat) and pd.notna(lon):
                        lats.append(lat)
                        lons.append(lon)
                        
            if len(lats) <= 1:
                cluster_scores.append(25.0)
                continue
                
            # Calcule le centre (centroid) de tous les apex de ce virage
            mean_lat = np.mean(lats)
            mean_lon = np.mean(lons)
            
            # Calcule la distance moyenne à ce centre (l'éparpillement / variance)
            dists = [_haversine_distance(lat, lon, mean_lat, mean_lon) for lat, lon in zip(lats, lons)]
            avg_spread = np.mean(dists)
            
            # Barème basé sur la dispersion spatiale (GPS +/- 1.5m de bruit habituel)
            # Très serré < 1.5m, Bon < 3.0m, Moyen < 6.0m
            if avg_spread <= 1.5:
                score = 30.0
            elif avg_spread <= 3.0:
                score = 25.0
            elif avg_spread <= 6.0:
                score = 20.0
            else:
                score = max(5.0, 30.0 * (1 - min(avg_spread / 12.0, 1.0)))
                
            cluster_scores.append(score)
            
        except Exception as e:
            warnings.warn(f"Error calculating precise apex clustering for corner {corner.get('id')}: {str(e)}")
            continue
            
    if not cluster_scores:
        return 20.0
        
    return float(np.mean(cluster_scores))


def calculate_trajectory_consistency_score(df: pd.DataFrame) -> float:
    """
    Calcule le score de régularité de trajectoire (0-25 points).
    
    Args:
        df: DataFrame avec colonnes curvature, heading
    
    Returns:
        Score entre 0 et 25
    """
    try:
        if 'curvature' not in df.columns:
            return 12.5  # Score moyen par défaut (25/2)
        
        curvature = pd.to_numeric(df['curvature'], errors='coerce').fillna(0).values
        
        # Écart-type de la courbure
        curvature_std = np.std(np.abs(curvature))
        
        # Détecter vraies corrections (seuil élevé pour éviter bruit vibrations/piste à 100Hz)
        STEERING_CORRECTION_THRESHOLD = 15.0  # degrés minimum (tolérance plus large)
        SMOOTHNESS_WINDOW = 10  # points de lissage
        if 'heading' in df.columns:
            heading = pd.to_numeric(df['heading'], errors='coerce').ffill().fillna(0).values
            if len(heading) > SMOOTHNESS_WINDOW:
                heading_series = pd.Series(heading)
                heading_smooth = heading_series.rolling(window=SMOOTHNESS_WINDOW, center=True, min_periods=1).mean().values
                heading_diff = np.diff(heading_smooth)
                heading_diff = np.where(heading_diff > 180, heading_diff - 360, heading_diff)
                heading_diff = np.where(heading_diff < -180, heading_diff + 360, heading_diff)
                corrections = np.sum(np.abs(heading_diff) > STEERING_CORRECTION_THRESHOLD)
            else:
                heading_diff = np.diff(heading)
                heading_diff = np.where(heading_diff > 180, heading_diff - 360, heading_diff)
                heading_diff = np.where(heading_diff < -180, heading_diff + 360, heading_diff)
                corrections = np.sum(np.abs(heading_diff) > STEERING_CORRECTION_THRESHOLD)
            correction_ratio = corrections / len(heading_diff) if len(heading_diff) > 0 else 0
        else:
            correction_ratio = 0
        
        # Score basé sur écart-type et corrections (max 25 pts)
        consistency_from_std = 25.0 * (1 - min(curvature_std / 0.5, 1.0))
        consistency_from_corrections = 25.0 * (1 - min(correction_ratio * 3, 1.0))
        score = (consistency_from_std * 0.6 + consistency_from_corrections * 0.4)
        
        return max(0.0, min(25.0, score))
    
    except Exception as e:
        warnings.warn(f"Error calculating trajectory consistency: {str(e)}")
        return 12.5


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
    if avg_efficiency >= 85.0:
        score = 25.0
    elif avg_efficiency >= 75.0:
        score = 20.0
    elif avg_efficiency >= 60.0:
        score = 15.0
    else:
        score = max(5.0, 15.0 * (avg_efficiency / 60.0))
    
    return score


def calculate_sector_times_score(
    df: pd.DataFrame,
    corner_details: List[Dict[str, Any]]
) -> float:
    """
    Calcule le score des temps secteurs (0-20 points).
    Sans multiples tours de référence, utilise l'efficacité vitesse
    des virages à l'intérieur des secteurs pour estimer le potentiel.
    """
    try:
        if 'cumulative_distance' not in df.columns or 'time' not in df.columns:
            return 10.0
            
        score = 14.0 # Base 14/20
        if corner_details:
            efficiencies = [c.get('speed_efficiency_pct', 80.0) for c in corner_details if 'speed_efficiency_pct' in c]
            if efficiencies:
                eff_ratio = np.clip(np.mean(efficiencies) / 100.0, 0.4, 1.0)
                score = eff_ratio * 20.0
            else:
                score = 15.0
                
        return min(20.0, score)
    
    except Exception as e:
        warnings.warn(f"Error calculating sector times score: {str(e)}")
        return 10.0


def calculate_performance_score(
    df: pd.DataFrame,
    corner_details: List[Dict[str, Any]],
    track_condition: str = "dry",
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
        
        # 2. Régularité Trajectoire (25 points)
        trajectory_consistency = calculate_trajectory_consistency_score(df)
        
        # 3. Vitesse Apex (25 points)
        apex_speed = calculate_apex_speed_score(corner_details)
        
        # 4. Temps Secteur (20 points)
        sector_times = calculate_sector_times_score(df, corner_details)
        
        # Source de vérité unique : overall_score = somme du breakdown (total 100 pts)
        overall_score = apex_precision + trajectory_consistency + apex_speed + sector_times
        
        # Grade (sera recalculé dans le service si score = moyenne virages)
        if overall_score >= 80:
            grade = "A"
        elif overall_score >= 70:
            grade = "B"
        elif overall_score >= 55:
            grade = "C"
        elif overall_score >= 40:
            grade = "D"
        else:
            grade = "F"
        
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
        
        breakdown = {
            "apex_precision": round(min(30.0, apex_precision), 1),
            "trajectory_consistency": round(min(25.0, trajectory_consistency), 1),
            "apex_speed": round(min(25.0, apex_speed), 1),
            "sector_times": round(min(20.0, sector_times), 1)
        }
        conditions_bonus = 0.0
        cond = (track_condition or "dry").lower()
        if cond == "wet":
            conditions_bonus = 5.0
        elif cond == "rain":
            conditions_bonus = 10.0
        if conditions_bonus > 0:
            breakdown["conditions_bonus"] = round(conditions_bonus, 1)
        overall_score = round(min(100.0, sum(breakdown.values())), 1)
        if overall_score >= 80:
            grade = "A"
        elif overall_score >= 70:
            grade = "B"
        elif overall_score >= 55:
            grade = "C"
        elif overall_score >= 40:
            grade = "D"
        else:
            grade = "F"
        percentile = int(min(99, max(10, 10 + (overall_score - 50) * 1.5)))
        return {
            "overall_score": overall_score,
            "breakdown": breakdown,
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
                "trajectory_consistency": 12.5,
                "apex_speed": 12.5,
                "sector_times": 10.0
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


def validate_score_consistency(score_data: Dict[str, Any]) -> None:
    """
    Vérifie que overall_score = sum(breakdown). Si écart > 0.5, log une erreur
    et force overall_score = sum(breakdown) pour cohérence API / graphiques.
    """
    breakdown = score_data.get("breakdown", {})
    if not breakdown:
        return
    total = sum(float(v) for v in breakdown.values())
    overall = float(score_data.get("overall_score", 0))
    if abs(total - overall) > 0.5:
        import logging
        logging.getLogger(__name__).error(
            "CRITICAL: score inconsistency overall_score=%.1f != sum(breakdown)=%.1f; forcing overall_score=sum(breakdown)",
            overall, total
        )
        score_data["overall_score"] = round(total, 1)
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
