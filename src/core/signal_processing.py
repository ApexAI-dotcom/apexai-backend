#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Signal Processing
Traitement et lissage des signaux GPS pour préserver les apex de virages
"""

import pandas as pd
import numpy as np
from scipy.signal import savgol_filter
from typing import Dict, Any, Tuple
import warnings


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
    R = 6371000  # Rayon de la Terre en mètres
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    
    a = np.sin(delta_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    return R * c


def calculate_snr(original: np.ndarray, filtered: np.ndarray) -> float:
    """
    Calcule le Signal-to-Noise Ratio (SNR) en décibels.
    
    Args:
        original: Signal original (bruité)
        filtered: Signal filtré
    
    Returns:
        SNR en décibels (dB). Retourne 0.0 si division par zéro.
    """
    if len(original) != len(filtered):
        return 0.0
    
    signal_power = np.var(filtered)
    noise = original - filtered
    noise_power = np.var(noise)
    
    # Éviter division par zéro
    if noise_power == 0 or signal_power == 0:
        return 0.0
    
    snr_linear = signal_power / noise_power
    
    # Convertir en dB : SNR_db = 10 * log10(SNR_linear)
    snr_db = 10 * np.log10(snr_linear)
    
    return float(snr_db)


def apply_savgol_filter(
    df: pd.DataFrame,
    lat_col: str = 'latitude',
    lon_col: str = 'longitude'
) -> pd.DataFrame:
    """
    Applique un filtre Savitzky-Golay pour lisser les données GPS
    tout en préservant les apex des virages.
    
    Le filtrage est adaptatif : la fenêtre s'ajuste automatiquement
    selon la taille du dataset pour optimiser la qualité.
    
    Args:
        df: DataFrame contenant les données GPS
        lat_col: Nom de la colonne de latitude (défaut: 'latitude')
        lon_col: Nom de la colonne de longitude (défaut: 'longitude')
    
    Returns:
        DataFrame avec colonnes ajoutées :
        - 'latitude_smooth' : Latitude lissée
        - 'longitude_smooth' : Longitude lissée
        - 'latitude_raw' : Latitude originale (copie)
        - 'longitude_raw' : Longitude originale (copie)
        
        Métadonnées disponibles dans df.attrs['filtering']
    
    Raises:
        ValueError: Si le DataFrame est trop petit ou colonnes manquantes
    """
    # VALIDATION INITIALE
    if len(df) < 10:
        raise ValueError(f"❌ DataFrame trop petit : {len(df)} lignes (minimum 10 requis)")
    
    if lat_col not in df.columns:
        raise ValueError(f"❌ Colonne '{lat_col}' introuvable")
    
    if lon_col not in df.columns:
        raise ValueError(f"❌ Colonne '{lon_col}' introuvable")
    
    df_result = df.copy()
    
    # Conserver les colonnes originales
    df_result['latitude_raw'] = df_result[lat_col].copy()
    df_result['longitude_raw'] = df_result[lon_col].copy()
    
    # Convertir en numérique si nécessaire
    lat_values = pd.to_numeric(df_result[lat_col], errors='coerce').values
    lon_values = pd.to_numeric(df_result[lon_col], errors='coerce').values
    
    # Supprimer les NaN pour le filtrage
    valid_mask = ~(np.isnan(lat_values) | np.isnan(lon_values))
    
    if valid_mask.sum() < 10:
        raise ValueError(f"❌ Pas assez de points GPS valides : {valid_mask.sum()} (minimum 10 requis)")
    
    lat_clean = lat_values[valid_mask]
    lon_clean = lon_values[valid_mask]
    
    # CALCUL PARAMÈTRES AUTOMATIQUES
    n_points = len(lat_clean)
    
    # Calcul adaptatif basé sur la fréquence d'échantillonnage
    if 'time' in df.columns and len(df) > 1:
        # Calculer fréquence d'échantillonnage
        time_diff = df['time'].diff().dropna()
        avg_sample_rate = 1.0 / time_diff.mean() if time_diff.mean() > 0 else 10
        
        # Fenêtre de 1-2 secondes (optimal pour karting)
        # GPS 10 Hz → window ~15, GPS 100 Hz → window ~150
        window_length = int(avg_sample_rate * 1.5)
        
        # Contraintes
        window_length = max(11, min(window_length, n_points//10))  # Max 10% des données
    else:
        # Fallback si pas de colonne time
        window_length = max(11, min(51, n_points//10))
    
    # Toujours impair
    if window_length % 2 == 0:
        window_length += 1
    
    # Ajuster si window_length > n_points
    if window_length >= n_points:
        # Utiliser le plus grand impair < n_points
        window_length = n_points - 1 if (n_points - 1) % 2 == 1 else n_points - 2
        window_length = max(3, window_length)  # Minimum 3
    
    # polyorder = 3 (optimal pour trajectoires courbes)
    polyorder = 3
    
    # Ajuster polyorder si trop grand par rapport à window_length
    if polyorder >= window_length:
        polyorder = max(2, window_length - 1)
    
    # APPLICATION FILTRE Savitzky-Golay
    try:
        lat_smooth = savgol_filter(
            lat_clean,
            window_length=window_length,
            polyorder=polyorder,
            mode='interp'  # Interpolation aux bords sans distorsion
        )
        
        lon_smooth = savgol_filter(
            lon_clean,
            window_length=window_length,
            polyorder=polyorder,
            mode='interp'
        )
    except Exception as e:
        raise ValueError(f"❌ Erreur lors de l'application du filtre : {str(e)}")
    
    # Réinsérer dans le DataFrame complet (NaN où invalide)
    lat_smooth_full = np.full(len(df_result), np.nan)
    lon_smooth_full = np.full(len(df_result), np.nan)
    
    lat_smooth_full[valid_mask] = lat_smooth
    lon_smooth_full[valid_mask] = lon_smooth
    
    df_result['latitude_smooth'] = lat_smooth_full
    df_result['longitude_smooth'] = lon_smooth_full
    
    # CALCUL QUALITÉ (SNR)
    snr_lat = calculate_snr(lat_clean, lat_smooth)
    snr_lon = calculate_snr(lon_clean, lon_smooth)
    snr_avg = (snr_lat + snr_lon) / 2.0
    
    # Déterminer la qualité
    if snr_avg > 25:
        quality = "excellent"
    elif snr_avg >= 15:
        quality = "good"
    else:
        quality = "poor"
    
    # Ajouter colonne de qualité
    df_result['filtering_quality'] = quality
    
    # VALIDATION : Distance moyenne déplacée par le filtrage
    displacements = []
    for i in range(len(lat_clean)):
        if not (np.isnan(lat_clean[i]) or np.isnan(lon_clean[i]) or 
                np.isnan(lat_smooth[i]) or np.isnan(lon_smooth[i])):
            dist = _haversine_distance(
                float(lat_clean[i]), float(lon_clean[i]),
                float(lat_smooth[i]), float(lon_smooth[i])
            )
            displacements.append(dist)
    
    avg_displacement = np.mean(displacements) if displacements else 0.0
    
    # Stocker les métadonnées dans attrs
    df_result.attrs['filtering'] = {
        'window_length': int(window_length),
        'polyorder': int(polyorder),
        'snr_db': float(snr_avg),
        'quality': quality,
        'avg_displacement_m': float(avg_displacement)
    }
    
    return df_result
