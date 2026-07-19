#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Profils de périphériques d'acquisition (transpondeurs / dataloggers)

Objectif : rendre le pipeline agnostique au matériel de manière PRO :
  1. Identifier l'appareil source depuis la signature de l'en-tête du fichier
     (AiM/MoTeC, RaceStudio, Alfano, Unipro, générique).
  2. Produire un RAPPORT DE DIAGNOSTIC d'import : appareil détecté, fréquence
     d'échantillonnage, canaux trouvés / manquants / non mappés, métadonnées.

Ce rapport a deux usages :
  - côté pilote : comprendre pourquoi une analyse est complète ou partielle ;
  - côté ApexAI : collecter la structure des formats encore inconnus pour
    écrire leurs profils au fur et à mesure (approche data-driven, pas de
    support "fictif" codé à l'aveugle).

NB : les profils Alfano/Unipro sont des SQUELETTES de détection — le mapping
fin de leurs canaux sera complété dès réception de fichiers réels de pilotes.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Canaux standardisés du pipeline et leur importance
REQUIRED_CHANNELS = {"time", "latitude", "longitude"}          # sans eux : analyse impossible
CORE_CHANNELS = {"speed"}                                       # dérivable du GPS si absent
ENRICHMENT_CHANNELS = {                                         # analyses bonus si présents
    "rpm": "Régime moteur (analyse mécanique Mon Kart)",
    "lateral_g": "G latéral mesuré (sinon dérivé du GPS)",
    "water temp": "Température d'eau (santé moteur)",
    "exhaust temp": "Température d'échappement (carburation)",
    "gps altitude": "Altitude (relief du circuit — à venir)",
    "accelerometerz": "Accéléro vertical (revêtement — à venir)",
}

# Signatures d'identification par appareil (motifs cherchés dans l'en-tête brut)
DEVICE_SIGNATURES = [
    {
        "device": "AiM (export MoTeC CSV)",
        "family": "aim",
        "patterns": [r'"Format",\s*"MoTeC CSV File"', r'"Device",\s*"AiM'],
        "min_matches": 1,
    },
    {
        "device": "AiM RaceStudio",
        "family": "aim",
        "patterns": [r"RaceStudio", r"AIM CSV File", r'"Session",'],
        "min_matches": 1,
    },
    {
        "device": "MoTeC",
        "family": "motec",
        "patterns": [r'"Format",\s*"MoTeC'],
        "min_matches": 1,
    },
    {
        # Squelette : à affiner avec de vrais exports Alfano (ADA/CSV)
        "device": "Alfano",
        "family": "alfano",
        "patterns": [r"Alfano", r"ALFANO"],
        "min_matches": 1,
    },
    {
        # Squelette : à affiner avec de vrais exports Unipro
        "device": "Unipro",
        "family": "unipro",
        "patterns": [r"Unipro", r"UNIPRO", r"UniGo"],
        "min_matches": 1,
    },
]


def read_header_lines(file_path: str, max_lines: int = 25) -> List[str]:
    """Lit les premières lignes brutes du fichier (tolérant aux encodages)."""
    lines: List[str] = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.rstrip("\n"))
    except Exception as e:
        logger.warning(f"device_profiles: header read failed: {e}")
    return lines


def identify_device(header_lines: List[str]) -> Dict[str, Any]:
    """Identifie l'appareil source depuis l'en-tête. Retourne device/family/metadata."""
    header_blob = "\n".join(header_lines)

    detected = {"device": "Générique / inconnu", "family": "generic"}
    for sig in DEVICE_SIGNATURES:
        matches = sum(1 for p in sig["patterns"] if re.search(p, header_blob))
        if matches >= sig["min_matches"]:
            detected = {"device": sig["device"], "family": sig["family"]}
            break

    # Métadonnées usuelles des en-têtes MoTeC/AiM ("Clé","Valeur",...)
    meta: Dict[str, str] = {}
    for key, field in (("Venue", "venue"), ("Driver", "driver"),
                       ("Device", "device_raw"), ("Sample Rate", "sample_rate"),
                       ("Log Date", "log_date"), ("Duration", "duration")):
        m = re.search(rf'"{key}",\s*"([^"]*)"', header_blob)
        if m and m.group(1).strip():
            meta[field] = m.group(1).strip()

    detected["metadata"] = meta
    return detected


def build_import_diagnostics(
    file_path: str,
    original_columns: List[str],
    normalized_columns: List[str],
    sample_rate_hz: Optional[float] = None,
) -> Dict[str, Any]:
    """Construit le rapport de diagnostic d'import.

    original_columns : colonnes brutes du CSV (avant normalisation)
    normalized_columns : colonnes après mapping (noms standardisés pipeline)
    """
    header = read_header_lines(file_path)
    device = identify_device(header)

    norm_set = {c.lower().strip() for c in normalized_columns}

    required_missing = sorted(REQUIRED_CHANNELS - norm_set)
    core_missing = sorted(CORE_CHANNELS - norm_set)
    enrichment_found = {ch: desc for ch, desc in ENRICHMENT_CHANNELS.items() if ch in norm_set}
    enrichment_missing = {ch: desc for ch, desc in ENRICHMENT_CHANNELS.items() if ch not in norm_set}

    # Colonnes du fichier qui n'ont pas été reconnues par le mapping.
    # Une colonne originale est "mappée" si son nom minuscule est soit déjà
    # standard, soit une variante connue du mapping du data_loader.
    try:
        from src.core.data_loader import get_known_column_aliases
        known_aliases = get_known_column_aliases()
    except Exception:
        known_aliases = set()
    known_after = norm_set | set(ENRICHMENT_CHANNELS) | known_aliases
    unmapped = sorted({
        c.strip() for c in original_columns
        if c and c.lower().strip() not in known_after and len(c.strip()) > 1
    })[:15]

    # Fréquence : header AiM prioritaire, sinon valeur calculée
    rate = None
    raw_rate = device.get("metadata", {}).get("sample_rate")
    if raw_rate:
        try:
            rate = float(re.sub(r"[^0-9.]", "", raw_rate))
        except ValueError:
            pass
    if rate is None and sample_rate_hz:
        rate = round(float(sample_rate_hz), 1)

    quality = "complete"
    if required_missing:
        quality = "unusable"
    elif core_missing or len(enrichment_found) == 0:
        quality = "partial"

    return {
        "device": device["device"],
        "device_family": device["family"],
        "metadata": device.get("metadata", {}),
        "sample_rate_hz": rate,
        "channels": {
            "required_missing": required_missing,
            "core_missing": core_missing,
            "enrichment_found": sorted(enrichment_found.keys()),
            "enrichment_missing": enrichment_missing,   # {canal: ce que ça débloquerait}
            "unmapped": unmapped,                        # à étudier pour de futurs profils
        },
        "quality": quality,  # complete | partial | unusable
    }
