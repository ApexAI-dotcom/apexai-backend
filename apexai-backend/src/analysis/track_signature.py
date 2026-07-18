#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Track Signature
Dérive une signature de piste réelle à partir des virages détectés par
detect_corners() (geometry.py) et du DataFrame de télémétrie.

Sortie alignée avec le format attendu par le frontend (CircuitCard.tsx) :
    speed_ratio      : 'sinueux' | 'mixte' | 'rapide'
    rotation         : 'horaire' | 'anti-horaire'
    hairpins_count   : int
    fast_corners_count : int
    elevation / bumpiness : None (non dérivables sans altitude / accéléro
                            vertical dans les CSV — laissés à la saisie user)
    + métriques bonus : corners_total, track_length_m, avg_apex_speed_kmh

Les seuils sont calibrés karting :
    - épingle : apex < HAIRPIN_APEX_KMH (freinage fort, quasi-arrêt)
    - virage rapide : apex > FAST_APEX_KMH (virage pris quasiment à fond)
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

HAIRPIN_APEX_KMH = 45.0
FAST_APEX_KMH = 85.0

# Bornes de vitesse apex moyenne pour le caractère global de la piste
SINUEUX_MEAN_APEX_KMH = 55.0
RAPIDE_MEAN_APEX_KMH = 75.0


def _median_lap_length_m(df: pd.DataFrame) -> Optional[float]:
    """Longueur médiane d'un tour à partir de cumulative_distance par tour."""
    if "cumulative_distance" not in df.columns or "lap_number" not in df.columns:
        return None
    try:
        lengths: List[float] = []
        for _, lap_df in df.groupby("lap_number"):
            dist = pd.to_numeric(lap_df["cumulative_distance"], errors="coerce").dropna()
            if len(dist) < 10:
                continue
            length = float(dist.max() - dist.min())
            if length > 100.0:  # ignore les fragments de tour
                lengths.append(length)
        if not lengths:
            return None
        # La médiane écarte naturellement les tours partiels (in/out laps)
        return round(float(np.median(lengths)), 1)
    except Exception as e:
        logger.warning(f"track_signature: lap length failed: {e}")
        return None


def compute_track_signature(
    corner_details: List[Dict[str, Any]],
    df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Calcule la signature de piste depuis les virages détectés.
    Retourne toujours un dict ; les champs non dérivables valent None
    (le frontend applique alors ses propres fallbacks).
    """
    signature: Dict[str, Any] = {
        "speed_ratio": None,
        "rotation": None,
        "hairpins_count": None,
        "fast_corners_count": None,
        "elevation": None,   # nécessite un canal altitude dans le CSV
        "bumpiness": None,   # nécessite un accéléro vertical dans le CSV
        "corners_total": None,
        "track_length_m": None,
        "avg_apex_speed_kmh": None,
    }

    if df is not None:
        signature["track_length_m"] = _median_lap_length_m(df)

    corners = [c for c in (corner_details or []) if isinstance(c, dict)]
    if not corners:
        logger.info("track_signature: aucun virage détecté, signature vide")
        return signature

    apex_speeds: List[float] = []
    left_count = 0
    right_count = 0
    hairpins = 0
    fast_corners = 0

    for c in corners:
        apex = c.get("apex_speed_kmh")
        if isinstance(apex, (int, float)) and apex > 0:
            apex_speeds.append(float(apex))
            if apex < HAIRPIN_APEX_KMH:
                hairpins += 1
            elif apex > FAST_APEX_KMH:
                fast_corners += 1

        ctype = str(c.get("type", "")).lower()
        if ctype == "left":
            left_count += 1
        elif ctype == "right":
            right_count += 1

    total = len(corners)
    signature["corners_total"] = total
    signature["hairpins_count"] = hairpins
    signature["fast_corners_count"] = fast_corners

    # Sens de rotation : une piste horaire est dominée par les virages à droite
    if left_count != right_count:
        signature["rotation"] = "anti-horaire" if left_count > right_count else "horaire"

    # Caractère de la piste : vitesse apex moyenne, ajustée par la composition
    if apex_speeds:
        mean_apex = float(np.mean(apex_speeds))
        signature["avg_apex_speed_kmh"] = round(mean_apex, 1)

        if mean_apex < SINUEUX_MEAN_APEX_KMH:
            speed_ratio = "sinueux"
        elif mean_apex > RAPIDE_MEAN_APEX_KMH:
            speed_ratio = "rapide"
        else:
            speed_ratio = "mixte"

        # Ajustement par composition : une piste "mixte" avec une écrasante
        # majorité d'épingles (ou de virages rapides) bascule de catégorie.
        analyzed = len(apex_speeds)
        if speed_ratio == "mixte" and analyzed >= 4:
            if hairpins / analyzed >= 0.5 and fast_corners == 0:
                speed_ratio = "sinueux"
            elif fast_corners / analyzed >= 0.5 and hairpins == 0:
                speed_ratio = "rapide"
        signature["speed_ratio"] = speed_ratio

    logger.info(
        "track_signature: %s virages (%s épingles, %s rapides), rotation=%s, "
        "ratio=%s, longueur=%sm",
        total, hairpins, fast_corners,
        signature["rotation"], signature["speed_ratio"], signature["track_length_m"],
    )
    return signature
