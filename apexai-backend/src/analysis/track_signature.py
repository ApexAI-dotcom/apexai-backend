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

Nature d'un virage — RELATIVE à la vitesse de pointe de la session :
    - épingle : vitesse au point de corde < 56 % de la vitesse de pointe ;
    - rapide  : >= 80 % de la vitesse de pointe ;
    - moyen   : entre les deux.
Avec des seuils fixes en km/h (45 / 85), un circuit rapide parcouru en X30 ou
en KZ n'avait « aucune épingle », et les virages moyens n'étaient comptés
nulle part (« 12 virages, 0 épingle, 4 rapides »). La même piste donne
désormais la même répartition quel que soit le kart : épingles + moyens +
rapides = nombre de virages. L'angle du virage (cap à l'entrée et à la sortie)
sert de garde-fou : un virage de moins de 70° n'est jamais une épingle.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Seuils relatifs (vitesse au point de corde / vitesse de pointe)
HAIRPIN_RATIO = 0.56
FAST_RATIO = 0.80
# Un virage plus ouvert que ça n'est jamais une épingle (garde-fou géométrique)
HAIRPIN_MIN_ANGLE_DEG = 70.0
# Repli si la vitesse de pointe est inconnue (anciens seuils absolus)
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


def _top_speed_kmh(df: Optional[pd.DataFrame]) -> Optional[float]:
    """Vitesse de pointe de la session : 98e centile, pour ignorer un pic GPS."""
    if df is None or "speed" not in df.columns:
        return None
    try:
        d = df[df["lap_number"] >= 1] if "lap_number" in df.columns else df
        v = pd.to_numeric(d["speed"], errors="coerce").dropna().values
        v = v[v > 5]
        if len(v) < 50:
            return None
        return float(np.percentile(v, 98))
    except Exception:
        return None


def _corner_angle_deg(df: Optional[pd.DataFrame], corner: Dict[str, Any]) -> Optional[float]:
    """Changement de cap entre l'entrée et la sortie du virage, en degrés."""
    if df is None or "heading" not in df.columns:
        return None
    a, b = corner.get("entry_index"), corner.get("exit_index")
    if a is None or b is None:
        return None
    try:
        seg = pd.to_numeric(df.loc[a:b, "heading"], errors="coerce").ffill().bfill().values
        if len(seg) < 2:
            return None
        h = np.unwrap(np.deg2rad(seg))
        return float(abs(np.rad2deg(h[-1] - h[0])))
    except Exception:
        return None


def classify_corner(apex_kmh: float, top_kmh: Optional[float], angle_deg: Optional[float]) -> str:
    """'epingle' | 'moyen' | 'rapide' — voir l'en-tête du module."""
    if top_kmh and top_kmh > 0:
        ratio = apex_kmh / top_kmh
        if ratio < HAIRPIN_RATIO and (angle_deg is None or angle_deg >= HAIRPIN_MIN_ANGLE_DEG):
            return "epingle"
        if ratio >= FAST_RATIO:
            return "rapide"
        return "moyen"
    if apex_kmh < HAIRPIN_APEX_KMH:
        return "epingle"
    if apex_kmh > FAST_APEX_KMH:
        return "rapide"
    return "moyen"


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
        "medium_corners_count": None,
        "fast_corners_count": None,
        "corner_kinds": [],
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
    medium = 0
    fast_corners = 0
    top = _top_speed_kmh(df)
    kinds: List[Dict[str, Any]] = []

    for c in corners:
        apex = c.get("apex_speed_kmh")
        if isinstance(apex, (int, float)) and apex > 0:
            apex_speeds.append(float(apex))
            kind = classify_corner(float(apex), top, _corner_angle_deg(df, c))
            if kind == "epingle":
                hairpins += 1
            elif kind == "rapide":
                fast_corners += 1
            else:
                medium += 1
            kinds.append({"corner_number": c.get("corner_number"), "kind": kind})

        ctype = str(c.get("type", "")).lower()
        if ctype == "left":
            left_count += 1
        elif ctype == "right":
            right_count += 1

    total = len(corners)
    signature["corners_total"] = total
    signature["hairpins_count"] = hairpins
    signature["medium_corners_count"] = medium
    signature["fast_corners_count"] = fast_corners
    signature["corner_kinds"] = kinds
    signature["top_speed_kmh"] = round(top, 1) if top else None

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
