#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Import natif des fichiers AiM RaceStudio (.xrk / .xrz)

Le pipeline d'analyse consomme le CSV « MoTeC CSV File » qu'exporte RaceStudio
(en-tête de 14 lignes, Beacon Markers, noms de canaux AiM). Plutôt que de
dupliquer la logique d'analyse, on convertit le .xrk vers CE MÊME format : les
passages sur la ligne (beacons), le circuit et les canaux utiles sont repris
du fichier natif, et data_loader / geometry / kart_mechanical restent inchangés.

Lecture du binaire : libxrk (MIT, https://github.com/m3rlin45/libxrk).
Les valeurs sont écrites comme dans un export RaceStudio : vitesse GPS en m/s
(data_loader convertit en km/h), temps en secondes depuis le début de session.
"""

import asyncio
import csv
import io
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

XRK_EXTENSIONS = (".xrk", ".xrz")

# Canaux sans lesquels aucune analyse de trajectoire n'est possible.
_GPS_REQUIRED = ("GPS Latitude", "GPS Longitude", "GPS Speed")

# Noms libxrk -> noms d'un export CSV RaceStudio (ceux que le pipeline, et
# kart_mechanical en particulier, savent déjà reconnaître).
_RENAME = {
    "GPS_Satellites": "GPS Nsat",
    "GPS_LateralAcc": "GPS LatAcc",
    "GPS_InlineAcc": "GPS LonAcc",
    "GPS_Yaw_Rate": "GPS Gyro",
    "GPS_Position_Accuracy": "GPS PosAccuracy",
    "GPS_Velocity_Accuracy": "GPS SpdAccuracy",
    "Internal Batt": "Int Batt Voltage",
}

# Canaux internes du logger : aucun intérêt pour l'analyse pilote.
_DROP = {
    "TimePulseTick", "TimTpItow", "Predictive Time", "Best Run Diff",
    "Best Today Diff", "Prev Lap Diff", "Ref Lap Diff", "ZeroX5", "ZeroX50",
    "GPS_Fix", "GPS_pDOP", "Luminosity", "Distance Lap",
}


class XrkImportError(ValueError):
    """Fichier .xrk/.xrz illisible ou inexploitable (message affichable au pilote)."""


def is_xrk_filename(filename: Optional[str]) -> bool:
    """True si le nom de fichier a une extension AiM native (.xrk / .xrz)."""
    return bool(filename) and filename.lower().endswith(XRK_EXTENSIONS)


def _header_value(value: Any, max_len: int = 80) -> str:
    """Valeur d'en-tête sûre : data_loader / services découpent l'en-tête sur ',' et '"'."""
    text = "" if value is None else str(value)
    text = re.sub(r'[",\r\n]+', " ", text).strip()
    return text[:max_len]


def _crossing_times(laps) -> List[float]:
    """Passages sur la ligne (s) : début de chaque tour numéroté + fin des tours complets."""
    if laps is None or laps.num_rows == 0:
        return []
    rows = laps.to_pylist()
    times = set()
    for r in rows:
        if int(r["num"]) >= 1:
            times.add(int(r["start_time"]))
        if r.get("lap_type") == "full":
            times.add(int(r["end_time"]))
    return [t / 1000.0 for t in sorted(times) if t >= 0]


def _usable_channels(log) -> List[str]:
    """Canaux à exporter : GPS requis + canaux finis, non constants, hors canaux internes."""
    keep: List[str] = list(_GPS_REQUIRED)
    for name, table in log.channels.items():
        if name in keep or name in _DROP:
            continue
        try:
            values = table.column(name).to_numpy(zero_copy_only=False).astype(float)
        except Exception:
            continue  # canal non numérique
        if values.size < 2 or not np.all(np.isfinite(values)):
            continue  # capteur débranché (valeurs infinies / NaN)
        if float(values.max()) == float(values.min()):
            continue  # capteur absent (valeur constante)
        keep.append(name)
    return keep


def xrk_to_motec_csv(content: bytes) -> bytes:
    """Convertit le contenu d'un .xrk/.xrz en CSV « MoTeC CSV File » (UTF-8)."""
    try:
        from libxrk import aim_xrk
    except ImportError as e:  # pragma: no cover - dépendance déclarée dans requirements.txt
        raise XrkImportError("L'import de fichiers .xrk n'est pas disponible sur ce serveur.") from e

    try:
        log = aim_xrk(io.BytesIO(content))
    except Exception as e:
        logger.warning(f"xrk_unreadable: {type(e).__name__}: {str(e)[:120]}")
        raise XrkImportError(
            "Fichier .xrk illisible ou corrompu. Réessaie avec le fichier d'origine "
            "de Race Studio."
        ) from e

    # libxrk est tolérant : un fichier qui n'est pas un .xrk donne une session vide, sans exception.
    if not log.channels:
        raise XrkImportError(
            "Fichier .xrk illisible ou vide (aucun canal trouvé). Vérifie que c'est bien le fichier "
            "d'origine de l'enregistreur, tel qu'il sort de Race Studio."
        )

    missing = [c for c in _GPS_REQUIRED if c not in log.channels]
    if missing:
        raise XrkImportError(
            "Ce fichier .xrk ne contient pas de données GPS exploitables "
            f"(canaux absents : {', '.join(missing)}). Vérifie que le GPS de l'enregistreur "
            "était actif pendant la session."
        )

    channels = _usable_channels(log)
    aligned = log.resample_to_channel("GPS Latitude", channels)
    df = aligned.get_channels_as_table().to_pandas()
    df = df[df["timecodes"] >= 0].reset_index(drop=True)
    if len(df) < 10:
        raise XrkImportError("Ce fichier .xrk ne contient pas assez de données GPS (session trop courte).")

    time_s = df["timecodes"].to_numpy(dtype=float) / 1000.0
    dt = np.diff(time_s)
    sample_hz = int(round(1.0 / float(np.median(dt)))) if dt.size and np.median(dt) > 0 else 10
    duration = float(time_s[-1] - time_s[0])

    meta: Dict[str, Any] = log.metadata or {}
    beacons = _crossing_times(log.laps)
    logger.info(
        f"xrk_import: {len(df)} lignes, {sample_hz} Hz, {duration:.1f}s, "
        f"{len(beacons)} passages ligne, {len(channels)} canaux"
    )

    out_names = [_RENAME.get(c, c) for c in channels]
    units = []
    for c in channels:
        u = (log.channels[c].schema.field(c).metadata or {}).get(b"units", b"")
        units.append(u.decode("utf-8", "ignore").strip("\x00 "))

    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
    w.writerow(["Format", "MoTeC CSV File", "", "", "Workbook"])
    w.writerow(["Venue", _header_value(meta.get("Venue")), "", "", "Worksheet"])
    w.writerow(["Vehicle", _header_value(meta.get("Vehicle")), "", "", "Vehicle Desc"])
    w.writerow(["Driver", _header_value(meta.get("Driver")), "", "", "Engine ID"])
    w.writerow(["Device", "AiM XRK"])
    w.writerow(["Comment", "", "", "", "Session", ""])
    w.writerow(["Log Date", _header_value(meta.get("Log Date")), "", "", "Origin Time", "0", "s"])
    w.writerow(["Log Time", _header_value(meta.get("Log Time")), "", "", "Start Time", "0", "s"])
    w.writerow(["Sample Rate", str(sample_hz), "Hz", "", "End Time", f"{time_s[-1]:g}", "s"])
    w.writerow(["Duration", f"{duration:g}", "s", "", "Start Distance"])
    w.writerow(["Range", "entire outing", "", "", "End Distance"])
    w.writerow(["Beacon Markers", " ".join(f"{t:.3f}" for t in beacons)])
    buf.write("\n\n")  # lignes 13-14 : vides (skiprows=14 côté data_loader)
    w.writerow(["Time"] + out_names)
    w.writerow(["s"] + units)
    buf.write("\n\n")

    columns = [np.char.mod("%.3f", time_s)]
    for c in channels:
        arr = df[c].to_numpy(dtype=float)
        precision = "%.8f" if c in ("GPS Latitude", "GPS Longitude") else "%.4f"
        columns.append(np.char.mod(precision, arr))
    for row in zip(*columns):
        w.writerow(row)

    return buf.getvalue().encode("utf-8")


async def normalize_upload(content: bytes, filename: Optional[str]) -> Tuple[bytes, Optional[str]]:
    """
    Fichier uploadé -> (contenu CSV, nom de fichier .csv).

    Les fichiers natifs AiM (.xrk / .xrz) sont convertis vers le CSV « MoTeC CSV
    File » de RaceStudio ; les CSV passent tels quels. La conversion tourne dans
    un thread pour ne pas bloquer l'event loop. Lève XrkImportError (ValueError)
    si le fichier est illisible.
    """
    if not is_xrk_filename(filename):
        return content, filename
    loop = asyncio.get_event_loop()
    csv_bytes = await loop.run_in_executor(None, xrk_to_motec_csv, content)
    stem = os.path.splitext(os.path.basename(filename))[0]
    return csv_bytes, f"{stem}.csv"
