#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Lecture de l'en-tête des exports de télémétrie.

SOURCE UNIQUE. Les passages sur la ligne (Beacon Markers), le circuit et la
durée de la séance étaient lus par trois copies d'un même bout de code — dans
data_loader et dans deux routes de l'API — qui ne connaissaient qu'un format.

RaceStudio propose pourtant deux exports CSV, et ils n'écrivent pas les
passages de la même façon :

    MoTeC CSV File   "Beacon Markers","82.248 135.306 187.523 ..."
                     un seul champ, valeurs séparées par des espaces

    AiM CSV File     "Beacon Markers","48.911","93.082","136.086",...
                     un champ par valeur

Les trois copies ne lisaient que le premier champ. Sur un export AiM CSV, un
seul passage était donc retenu, et toute la séance qui le suivait devenait un
« tour » unique de plusieurs minutes — rejeté par le contrôle de cohérence
(« le meilleur temps calculé (391 s) est incohérent »). Tous les exports AiM
CSV échouaient, sans exception.

Seconde différence : l'export AiM CSV ajoute la FIN DE SÉANCE comme dernier
marqueur (sa valeur est égale à la durée, et postérieure au dernier
échantillon). Ce n'est pas un passage sur la ligne. On l'écarte, pour que les
marqueurs aient le même sens quel que soit le format : des franchissements de
ligne, rien d'autre.
"""

from __future__ import annotations

import csv
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Les métadonnées tiennent toujours dans les premières lignes du fichier ; au-delà
# commencent les noms de canaux puis les données.
_HEADER_MAX_LINES = 24

# Tolérance pour reconnaître le marqueur de fin de séance : RaceStudio écrit la
# durée et le dernier marqueur avec la même valeur, à l'arrondi près.
_SESSION_END_TOLERANCE_S = 0.05


def _floats(fields: List[str]) -> List[float]:
    """Tous les nombres présents dans une liste de champs, quel que soit le
    séparateur interne (espace pour MoTeC, un champ par valeur pour AiM)."""
    out: List[float] = []
    for field in fields:
        for tok in str(field).replace(";", " ").split():
            try:
                out.append(float(tok))
            except ValueError:
                continue
    return out


def _duration(value: str) -> Optional[float]:
    """« 439.994 » ou « 7:19.994 » → secondes."""
    value = (value or "").strip()
    if not value:
        return None
    m = re.match(r"^(?:(\d+):)?(\d+(?:\.\d+)?)$", value)
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + float(m.group(2))


def read_session_header(path: str) -> Dict[str, Any]:
    """
    Métadonnées d'un export de télémétrie.

    Returns:
        {
          "format":          "MoTeC CSV File" | "AiM CSV File" | None,
          "beacon_markers":  passages sur la ligne, triés (fin de séance exclue),
          "circuit_name":    circuit déclaré dans le boîtier, ou None,
          "duration_s":      durée de la séance, ou None,
          "segment_times_s": chronos d'origine du boîtier (AiM CSV), ou [],
        }

    Ne lève jamais : un en-tête illisible donne des champs vides, et le
    pipeline retombe alors sur la détection des tours par GPS.
    """
    info: Dict[str, Any] = {
        "format": None,
        "beacon_markers": [],
        "circuit_name": None,
        "duration_s": None,
        "segment_times_s": [],
    }
    labels: Dict[str, List[str]] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
            for i, row in enumerate(csv.reader(f)):
                if i >= _HEADER_MAX_LINES:
                    break
                if not row:
                    continue
                label = (row[0] or "").strip().strip('"').lower()
                if not label:
                    continue
                # Première occurrence seulement : la ligne des canaux commence
                # aussi par « Time », qui ne doit pas écraser une métadonnée.
                labels.setdefault(label, [c.strip() for c in row[1:]])
    except Exception as exc:  # pragma: no cover - fichier illisible
        logger.warning("read_session_header: %s", exc)
        return info

    fmt = (labels.get("format") or [""])[0].strip()
    info["format"] = fmt or None

    duration = _duration((labels.get("duration") or [""])[0])
    info["duration_s"] = duration

    # Circuit : « Venue » en MoTeC, « Session » en AiM CSV (RaceStudio y écrit
    # le nom de la piste). « Session » n'est retenu que pour ce format : dans un
    # export MoTeC, le mot apparaît aussi, mais jamais en tête de ligne.
    venue = (labels.get("venue") or [""])[0].strip()
    if not venue and fmt.lower().startswith("aim csv"):
        venue = (labels.get("session") or [""])[0].strip()
    info["circuit_name"] = venue or None

    markers = sorted(m for m in _floats(labels.get("beacon markers", [])) if m > 0)
    # Marqueur de fin de séance (AiM CSV) : ce n'est pas un passage sur la ligne.
    if markers and duration is not None and abs(markers[-1] - duration) <= _SESSION_END_TOLERANCE_S:
        markers = markers[:-1]
    info["beacon_markers"] = markers

    seg_fields = labels.get("segment times", [])
    info["segment_times_s"] = [t for t in (_duration(v) for v in seg_fields) if t is not None]

    return info


def read_beacon_markers(path: str) -> List[float]:
    """Raccourci : uniquement les passages sur la ligne."""
    return read_session_header(path)["beacon_markers"]
