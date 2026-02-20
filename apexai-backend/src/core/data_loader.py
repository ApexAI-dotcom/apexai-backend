#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Data Loader
Chargeur robuste de fichiers de télémétrie avec détection automatique de format
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import warnings

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    warnings.warn("DuckDB non disponible, fallback désactivé", UserWarning)


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule la distance en mètres entre deux points GPS
    en utilisant la formule de Haversine.
    
    Args:
        lat1: Latitude du premier point (degrés)
        lon1: Longitude du premier point (degrés)
        lat2: Latitude du second point (degrés)
        lon2: Longitude du second point (degrés)
    
    Returns:
        Distance en mètres entre les deux points
    """
    # Rayon de la Terre en mètres
    R = 6371000
    
    # Conversion en radians
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    
    # Formule de Haversine
    a = np.sin(delta_phi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    distance = R * c
    return distance


def _detect_format(file_path: str) -> int:
    """
    Détecte le format du fichier en lisant les premières lignes.
    
    Args:
        file_path: Chemin vers le fichier CSV
    
    Returns:
        Nombre de lignes à ignorer (skiprows)
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= 15:
                    break
                line_lower = line.lower()
                if 'mychron' in line_lower or 'aim' in line_lower:
                    return 14  # Format MyChron/AiM : skip 14 lignes
        return 0  # Format standard : pas de skip
    except Exception:
        return 0


def _parse_with_pandas(file_path: str, skiprows: int, encoding: str = 'utf-8') -> Optional[pd.DataFrame]:
    """
    Essaie de parser le fichier CSV avec pandas.
    
    Args:
        file_path: Chemin vers le fichier CSV
        skiprows: Nombre de lignes à ignorer
        encoding: Encodage à utiliser
    
    Returns:
        DataFrame si succès, None sinon
    """
    try:
        df = pd.read_csv(
            file_path,
            skiprows=skiprows,
            encoding=encoding,
            on_bad_lines='warn',
            low_memory=False
        )
        return df
    except Exception:
        return None


def _normalize_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Normalise les noms de colonnes : minuscules et mapping standard.
    Détecte et convertit les unités (m/s → km/h).
    
    Args:
        df: DataFrame à normaliser
    
    Returns:
        Tuple (DataFrame normalisé, liste de warnings)
    """
    df_normalized = df.copy()
    conversion_warnings = []
    
    # Convertir en minuscules et nettoyer
    df_normalized.columns = [col.lower().strip() for col in df_normalized.columns]
    
    # Mapping exhaustif des variantes de colonnes
    column_mapping = {
        # Latitude
        'lat': 'latitude',
        'gps latitude': 'latitude',
        'gps_latitude': 'latitude',
        'gps lat': 'latitude',
        'gps_lat': 'latitude',
        'lat_deg': 'latitude',
        'latitude_deg': 'latitude',
        'gpslat': 'latitude',
        'pos_lat': 'latitude',

        # Longitude
        'lon': 'longitude',
        'lng': 'longitude',
        'gps longitude': 'longitude',
        'gps_longitude': 'longitude',
        'gps lon': 'longitude',
        'gps_lon': 'longitude',
        'lon_deg': 'longitude',
        'longitude_deg': 'longitude',
        'gpslon': 'longitude',
        'pos_lon': 'longitude',
        'pos_lng': 'longitude',

        # Speed
        'vel': 'speed',
        'velocity': 'speed',
        'spd': 'speed',
        'gps speed': 'speed',
        'gps_speed': 'speed',
        'speed_kmh': 'speed',
        'speed_kph': 'speed',
        'vitesse': 'speed',
        'velocity_kmh': 'speed',
        'velocity_kph': 'speed',
        'vhw': 'speed',
        'sog': 'speed',

        # Time
        't': 'time',
        'timestamp': 'time',
        'elapsed time': 'time',
        'elapsed_time': 'time',
        'time_s': 'time',
        'time_ms': 'time',
        'temps': 'time',
        'session_time': 'time',
        'laptime': 'time',
        'lap_time': 'time',

        # Lateral G (bonus si présent)
        'lateral_g': 'lateral_g',
        'lat_g': 'lateral_g',
        'g_lat': 'lateral_g',
        'ay': 'lateral_g',
        'accel_lat': 'lateral_g',
    }

    # Appliquer le mapping
    df_normalized.rename(columns=column_mapping, inplace=True)

    # Fuzzy fallback : chercher colonnes contenant des mots-clés
    col_map = {}
    for col in df_normalized.columns:
        col_lower = col.lower()
        if 'lat' in col_lower and 'longitude' not in col_lower and 'latitude' not in col_lower:
            col_map[col] = 'latitude'
        elif 'lon' in col_lower and 'latitude' not in col_lower and 'longitude' not in col_lower:
            col_map[col] = 'longitude'
        elif ('speed' in col_lower or 'vitesse' in col_lower or 'vel' in col_lower) and 'speed' not in df_normalized.columns:
            col_map[col] = 'speed'
        elif 'time' in col_lower and 'time' not in df_normalized.columns:
            col_map[col] = 'time'
    df_normalized.rename(columns=col_map, inplace=True)

    # CONVERSION m/s → km/h si nécessaire
    if 'speed' in df_normalized.columns:
        # Convertir en numérique pour analyse
        df_normalized['speed'] = pd.to_numeric(df_normalized['speed'], errors='coerce')
        
        # Détection : si vitesse max < 50, c'est probablement en m/s
        max_speed = df_normalized['speed'].max()
        if pd.notna(max_speed) and max_speed < 50:
            df_normalized['speed'] = df_normalized['speed'] * 3.6
            conversion_warnings.append("ℹ️  Vitesse convertie de m/s à km/h")
    
    return df_normalized, conversion_warnings


def _validate_data(df: pd.DataFrame) -> Tuple[bool, pd.DataFrame, List[str]]:
    """
    Valide les données du DataFrame.
    
    Args:
        df: DataFrame à valider
    
    Returns:
        Tuple (is_valid, cleaned_dataframe, list_of_warnings)
    """
    warnings_list = []
    df_clean = df.copy()
    
    # Vérifier nombre de lignes
    if len(df_clean) < 10:
        return False, df_clean, ["❌ Pas assez de données : moins de 10 lignes"]
    
    # Vérifier colonnes requises
    required_columns = ['latitude', 'longitude', 'speed']
    missing_columns = [col for col in required_columns if col not in df_clean.columns]
    
    if missing_columns:
        return False, df_clean, [f"❌ Colonnes manquantes : {', '.join(missing_columns)}"]
    
    # Convertir en numérique
    for col in required_columns:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
    
    # Vérifier GPS valides
    invalid_lat = ((df_clean['latitude'] < -90) | (df_clean['latitude'] > 90)).sum()
    invalid_lon = ((df_clean['longitude'] < -180) | (df_clean['longitude'] > 180)).sum()
    
    if invalid_lat > 0:
        warnings_list.append(f"⚠️ {invalid_lat} point(s) avec latitude invalide")
        df_clean = df_clean[(df_clean['latitude'] >= -90) & (df_clean['latitude'] <= 90)]
    
    if invalid_lon > 0:
        warnings_list.append(f"⚠️ {invalid_lon} point(s) avec longitude invalide")
        df_clean = df_clean[(df_clean['longitude'] >= -180) & (df_clean['longitude'] <= 180)]
    
    # Vérifier time croissant (si colonne time existe)
    if 'time' in df_clean.columns:
        df_clean['time'] = pd.to_numeric(df_clean['time'], errors='coerce')
        if not df_clean['time'].is_monotonic_increasing:
            warnings_list.append("⚠️ La colonne time n'est pas strictement croissante")
    
    # Vérifier qu'il reste assez de données après nettoyage
    if len(df_clean) < 10:
        return False, df_clean, ["❌ Pas assez de données après nettoyage : moins de 10 lignes valides"]
    
    return True, df_clean, warnings_list


def _calculate_metadata(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calcule les métadonnées du DataFrame.
    
    Args:
        df: DataFrame analysé
    
    Returns:
        Dictionnaire de métadonnées
    """
    metadata = {
        'rows': len(df),
        'columns': list(df.columns),
        'duration_seconds': None,
        'circuit_length_m': 0.0
    }
    
    # Calculer durée (si time disponible)
    if 'time' in df.columns and df['time'].notna().any():
        time_values = df['time'].dropna()
        if len(time_values) > 0:
            duration = float(time_values.max() - time_values.min())
            metadata['duration_seconds'] = duration
    
    # Calculer longueur du circuit (somme des distances Haversine)
    if len(df) > 1:
        total_distance = 0.0
        for i in range(1, len(df)):
            lat1 = df['latitude'].iloc[i-1]
            lon1 = df['longitude'].iloc[i-1]
            lat2 = df['latitude'].iloc[i]
            lon2 = df['longitude'].iloc[i]
            
            # Vérifier que les valeurs sont valides
            if (pd.notna(lat1) and pd.notna(lon1) and pd.notna(lat2) and pd.notna(lon2)):
                dist = _haversine_distance(float(lat1), float(lon1), float(lat2), float(lon2))
                total_distance += dist
        
        metadata['circuit_length_m'] = round(total_distance, 2)
    
    return metadata


def robust_load_telemetry(file_path: str) -> Dict[str, Any]:
    """
    Charge un fichier de télémétrie de manière robuste avec détection automatique.
    
    Cette fonction essaie plusieurs méthodes de parsing en cascade :
    1. pandas avec UTF-8
    2. pandas avec Latin-1
    3. pandas avec UTF-16
    4. DuckDB (si disponible)
    
    Args:
        file_path: Chemin vers le fichier CSV de télémétrie
    
    Returns:
        Dictionnaire avec :
        - success: bool - Indique si le chargement a réussi
        - data: pd.DataFrame | None - DataFrame des données (si succès)
        - format: str - Format détecté ('MyChron', 'AiM', 'Standard', etc.)
        - warnings: List[str] - Liste des avertissements
        - metadata: Dict - Métadonnées (rows, columns, duration, circuit_length)
        - error: str | None - Message d'erreur (si échec)
    """
    result = {
        'success': False,
        'data': None,
        'format': 'Unknown',
        'warnings': [],
        'metadata': {},
        'error': None
    }
    
    # Vérifier que le fichier existe
    if not Path(file_path).exists():
        result['error'] = f"❌ Fichier introuvable : {file_path}"
        return result
    
    # Détection du format (skiprows)
    skiprows = _detect_format(file_path)
    if skiprows > 0:
        result['format'] = 'MyChron/AiM'
    else:
        result['format'] = 'Standard'
    
    df = None
    
    # PARSING CASCADE - Essai 1 : pandas UTF-8
    try:
        df = _parse_with_pandas(file_path, skiprows, encoding='utf-8')
        if df is not None and len(df) > 0:
            result['warnings'].append("✓ Fichier chargé avec pandas (UTF-8)")
    except Exception as e:
        result['warnings'].append(f"⚠️ Échec pandas UTF-8 : {str(e)[:100]}")
    
    # PARSING CASCADE - Essai 2 : pandas Latin-1
    if df is None or len(df) == 0:
        try:
            df = _parse_with_pandas(file_path, skiprows, encoding='latin-1')
            if df is not None and len(df) > 0:
                result['warnings'].append("✓ Fichier chargé avec pandas (Latin-1)")
        except Exception as e:
            result['warnings'].append(f"⚠️ Échec pandas Latin-1 : {str(e)[:100]}")
    
    # PARSING CASCADE - Essai 3 : pandas UTF-16
    if df is None or len(df) == 0:
        try:
            df = _parse_with_pandas(file_path, skiprows, encoding='utf-16')
            if df is not None and len(df) > 0:
                result['warnings'].append("✓ Fichier chargé avec pandas (UTF-16)")
        except Exception as e:
            result['warnings'].append(f"⚠️ Échec pandas UTF-16 : {str(e)[:100]}")
    
    # PARSING CASCADE - Essai 4 : DuckDB (si disponible)
    if (df is None or len(df) == 0) and DUCKDB_AVAILABLE:
        try:
            conn = duckdb.connect()
            query = f"SELECT * FROM read_csv_auto('{file_path}', skip={skiprows})"
            df = conn.execute(query).df()
            conn.close()
            if df is not None and len(df) > 0:
                result['warnings'].append("✓ Fichier chargé avec DuckDB")
        except Exception as e:
            result['warnings'].append(f"⚠️ Échec DuckDB : {str(e)[:100]}")
    
    # Si toujours pas de données
    if df is None or len(df) == 0:
        result['error'] = "❌ Impossible de parser le fichier avec toutes les méthodes essayées"
        return result
    
    # Normalisation des colonnes
    try:
        df, norm_warnings = _normalize_columns(df)
        result['warnings'].extend(norm_warnings)

    except Exception as e:
        result['error'] = f"❌ Erreur lors de la normalisation : {str(e)}"
        return result
    
    # Validation des données
    is_valid, df_clean, validation_warnings = _validate_data(df)
    result['warnings'].extend(validation_warnings)
    
    if not is_valid:
        result['error'] = "❌ Validation des données échouée"
        if validation_warnings:
            result['error'] = validation_warnings[0]  # Premier message d'erreur
        return result
    
    # Utiliser le DataFrame nettoyé
    df = df_clean
    
    # Calcul des métadonnées
    try:
        result['metadata'] = _calculate_metadata(df)
    except Exception as e:
        result['warnings'].append(f"⚠️ Erreur calcul métadonnées : {str(e)[:100]}")
        result['metadata'] = {
            'rows': len(df),
            'columns': list(df.columns),
            'duration_seconds': None,
            'circuit_length_m': 0.0
        }
    
    # Succès !
    result['success'] = True
    result['data'] = df
    
    return result
