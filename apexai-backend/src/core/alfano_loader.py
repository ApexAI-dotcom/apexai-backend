#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Import des séances Alfano (Alfano 6 / 7, logiciel ADA).

Deux formats sortent du logiciel ADA, et les pilotes déposent l'un ou l'autre :

1. Export « Excel » : un CSV séparé par « ; », tous les tours à la suite.
   - « Time » repart de 0 à chaque tour ; « Absolute Time » n'est pas fiable
     (à 0 sur certains exports) : le temps de séance est recalculé à partir
     des chronos (« Time Lap », donnés sur la 1re ligne de chaque tour).
   - Séparateur de milliers « , » sur certains canaux (« 4,120 » tr/min,
     « 17,082 » d'orientation), alors que les décimales s'écrivent « . ».
   - Orientation en centièmes de degré sur certains exports, en degrés sur
     d'autres : ramenée en degrés.
   - Colonnes facultatives : T1 / T2, distance, pneus (pression / température
     par roue et par train).

2. Zip brut : un fichier LAP_n par tour à 10 Hz (valeurs entières : vitesse
   ÷10, lat/lon ÷1e6, altitude ÷10, orientation ÷100, G = (brut − 1000) ÷ 100),
   un résumé SN… (chronos en ms, min/max par canal, « max EGT »), la ligne de
   départ dans projection_orthogonale2023.csv et le nom du circuit et du pilote
   dans le résumé. Les colonnes « 25Hz » (vitesse, deltas lat/lon), quand elles
   existent, sont des mesures prises au milieu de l'intervalle : elles sont
   intercalées (≈ 20 Hz). Voir ALFANO7_FORMAT.md (rétro-ingénierie vérifiée
   contre l'export Excel).

Les deux sont convertis vers le CSV « MoTeC CSV File » déjà lu par le reste du
pipeline (comme les .xrk AiM) : passages sur la ligne = chronos de l'Alfano,
qui chronomètre lui-même sur sa ligne de départ.

T1 / T2 : capteurs de température branchés au choix du pilote (eau, culasse,
échappement…). On ne les range PAS en « température d'eau » : seule une voie
dont le maximum correspond au « max EGT » du résumé, ou qui dépasse nettement
ce qu'une eau peut atteindre (> 250 °C), est reconnue comme échappement.
Les autres restent « Alfano T1 / T2 », visibles mais non interprétées.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class AlfanoImportError(ValueError):
    """Séance Alfano illisible : message destiné au pilote."""


ALFANO_EXTENSIONS = {".zip"}
_THOUSANDS = re.compile(r"^-?\d{1,3}(,\d{3})+$")
EGT_MIN_C = 250.0
LEAD_S = 1.0


# ───────────────────────────────────────────────────────────── détection

def is_alfano_excel(content: bytes) -> bool:
    head = content[:400].decode("utf-8", "ignore").lstrip("﻿")
    first = head.splitlines()[0] if head else ""
    return first.startswith("Lap;Time Lap;") and "Lat." in first


def is_alfano_zip(content: bytes) -> bool:
    if not content.startswith(b"PK"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            return any(_base(n).upper().startswith("LAP_") and n.lower().endswith(".csv") for n in z.namelist())
    except zipfile.BadZipFile:
        return False


def _base(name: str) -> str:
    return name.replace("\\", "/").rsplit("/", 1)[-1]


# ───────────────────────────────────────────────────────────── utilitaires

def _num(series: pd.Series) -> pd.Series:
    """Nombres ADA : « 4,120 » = 4120 (milliers) ; les décimales sont des points."""
    s = series.astype(str).str.strip()
    s = s.where(~s.str.match(_THOUSANDS), s.str.replace(",", "", regex=False))
    s = s.str.replace(",", ".", regex=False)  # au cas où une décimale serait en virgule
    return pd.to_numeric(s, errors="coerce")


def _temp_channel(values: np.ndarray, name: str, egt_max: Optional[float]) -> Optional[Tuple[str, np.ndarray]]:
    """T1 / T2 → échappement si c'est prouvé, sinon voie neutre ; rien si vide."""
    v = values[np.isfinite(values)]
    if v.size == 0 or np.nanmax(np.abs(v)) == 0:
        return None
    vmax = float(np.nanmax(v))
    if (egt_max and abs(vmax - egt_max) <= max(15.0, 0.05 * egt_max)) or vmax > EGT_MIN_C:
        return "Exhaust Temp", values
    return f"Alfano {name}", values


def _motec_csv(
    *,
    time_s: np.ndarray,
    channels: List[Tuple[str, str, np.ndarray]],
    beacons: List[float],
    venue: str,
    driver: str,
    log_date: str,
    log_time: str,
    device: str,
    start_line: Optional[Dict[str, float]],
) -> bytes:
    """CSV « MoTeC CSV File » identique à celui produit pour les .xrk.

    L'Alfano n'enregistre qu'à partir du premier passage sur sa ligne : le
    fichier commence par un tour chronométré, pas par une sortie des stands.
    Le pipeline range tout ce qui précède le 1er passage en « tour 0 »
    (sortie des stands, ignorée) et un passage à t = 0 n'est pas lu : on décale
    la séance d'une seconde pour que le 1er passage soit vu et que le tour 1
    de l'Alfano reste le tour 1.
    """
    time_s = np.asarray(time_s, dtype=float) + LEAD_S
    beacons = [round(b + LEAD_S, 3) for b in beacons]
    dt = np.diff(time_s)
    hz = int(round(1.0 / float(np.median(dt)))) if dt.size and np.median(dt) > 0 else 10
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
    w.writerow(["Format", "MoTeC CSV File", "", "", "Workbook"])
    w.writerow(["Venue", venue, "", "", "Worksheet"])
    w.writerow(["Vehicle", "", "", "", "Vehicle Desc"])
    w.writerow(["Driver", driver, "", "", "Engine ID"])
    w.writerow(["Device", device])
    sl = f"{start_line['lat']:.6f} {start_line['lon']:.6f} {start_line['heading']:.1f}" if start_line else ""
    w.writerow(["Comment", f"Ligne de départ Alfano {sl}".strip() if sl else "", "", "", "Session", ""])
    w.writerow(["Log Date", log_date, "", "", "Origin Time", "0", "s"])
    w.writerow(["Log Time", log_time, "", "", "Start Time", "0", "s"])
    w.writerow(["Sample Rate", str(hz), "Hz", "", "End Time", f"{time_s[-1]:g}", "s"])
    w.writerow(["Duration", f"{time_s[-1] - time_s[0]:g}", "s", "", "Start Distance"])
    w.writerow(["Range", "entire outing", "", "", "End Distance"])
    w.writerow(["Beacon Markers", " ".join(f"{t:.3f}" for t in beacons)])
    buf.write("\n\n")
    w.writerow(["Time"] + [c[0] for c in channels])
    w.writerow(["s"] + [c[1] for c in channels])
    buf.write("\n\n")
    cols = [np.char.mod("%.3f", time_s)]
    for name, _, arr in channels:
        fmt = "%.7f" if name in ("GPS Latitude", "GPS Longitude") else "%.3f"
        a = np.where(np.isfinite(arr), arr, np.nan)
        cols.append(np.where(np.isfinite(a), np.char.mod(fmt, np.nan_to_num(a)), ""))
    for row in zip(*cols):
        w.writerow(row)
    return buf.getvalue().encode("utf-8")


def _check(lat: np.ndarray, lon: np.ndarray, n_laps: int):
    ok = np.isfinite(lat) & np.isfinite(lon) & (np.abs(lat) > 0.1) & (np.abs(lon) > 0.01)
    if ok.mean() < 0.5:
        raise AlfanoImportError("Cette séance Alfano n'a pas de position GPS exploitable : vérifie que le GPS était actif.")
    if n_laps < 1:
        raise AlfanoImportError("Aucun tour complet dans cette séance Alfano.")


# ───────────────────────────────────────────────────────────── export Excel

_TYRE = re.compile(r"^(Temp\. interne|Pressure) tyre (FL|FR|RL|RR) set ([AB])$")


def _from_filename(filename: Optional[str]) -> Dict[str, str]:
    """« Excel_SN894_090624_11H58_RENAUD__P__SOUCY_13_5105.csv » → date, heure, pilote, circuit."""
    out: Dict[str, str] = {}
    if not filename:
        return out
    stem = _base(filename).rsplit(".", 1)[0]
    m = re.match(r"(?:Excel_|ALFANO\d?_LAP_)?SN\d+_(\d{2})(\d{2})(\d{2})_(\d{2})H(\d{2})_(.+)$", stem, re.I)
    if not m:
        return out
    dd, mm, yy, hh, mi, rest = m.groups()
    out["log_date"] = f"{dd}/{mm}/20{yy}"
    out["log_time"] = f"{hh}:{mi}:00"
    parts = re.split(r"_+P_+", rest, maxsplit=1)
    if len(parts) == 2:
        out["driver"] = parts[0].replace("_", " ").strip().title()
        track = re.sub(r"(_+\d+)+$", "", parts[1])
        out["venue"] = track.replace("_", " ").strip()
    return out


def alfano_excel_to_motec_csv(content: bytes, filename: Optional[str] = None) -> bytes:
    fn = _from_filename(filename)
    text = content.decode("utf-8", "ignore").lstrip("﻿")
    first = text.splitlines()[0]
    m = re.search(r"UTC time\s*:\s*(\d{2})(\d{2})(\d{2})", first)
    log_time = f"{m.group(1)}:{m.group(2)}:{m.group(3)}" if m else ""
    df = pd.read_csv(io.StringIO(text), sep=";", dtype=str, keep_default_na=False, na_values=[""])
    df = df.loc[:, [c for c in df.columns if c and not c.startswith("UTC time") and not c.startswith("Unnamed")]]
    df = df[df["Time"].notna()].reset_index(drop=True)

    starts = df.index[df["Lap"].notna()].tolist()
    if not starts:
        raise AlfanoImportError("Export Alfano sans tours : réexporte la séance depuis ADA.")
    lap_times = _num(df.loc[starts, "Time Lap"]).to_numpy()
    lap_start = np.concatenate([[0.0], np.cumsum(lap_times)])
    lap_of_row = np.zeros(len(df), dtype=int)
    for k, s in enumerate(starts):
        lap_of_row[s:] = k
    t_in_lap = _num(df["Time"]).to_numpy()
    time_s = lap_start[lap_of_row] + t_in_lap

    lat, lon = _num(df["Lat."]).to_numpy(), _num(df["Lon."]).to_numpy()
    _check(lat, lon, len(starts))

    ch: List[Tuple[str, str, np.ndarray]] = [("GPS Latitude", "deg", lat), ("GPS Longitude", "deg", lon)]
    ch.append(("GPS Speed", "km/h", _num(df["Speed GPS"]).to_numpy()))
    if "RPM" in df:
        ch.append(("RPM", "rpm", _num(df["RPM"]).to_numpy()))
    if "Altitude" in df:
        ch.append(("GPS Altitude", "m", _num(df["Altitude"]).to_numpy()))
    if "Orientation" in df:
        o = _num(df["Orientation"]).to_numpy()
        if np.nanmax(np.abs(o)) > 400:  # centièmes de degré
            o = o / 100.0
        ch.append(("GPS Heading", "deg", o))
    if "Gf. X" in df:
        ch.append(("GPS LatAcc", "g", _num(df["Gf. X"]).to_numpy()))
    if "Gf. Y" in df:
        # Alfano : Gf. Y > 0 au freinage ; convention AiM : LonAcc > 0 en accélération.
        ch.append(("GPS LonAcc", "g", -_num(df["Gf. Y"]).to_numpy()))
    if "Speed rear" in df:
        sr = _num(df["Speed rear"]).to_numpy()
        if np.nanmax(sr) > 0:
            ch.append(("Speed Rear", "km/h", sr))
    for t in ("T1", "T2"):
        if t in df:
            r = _temp_channel(_num(df[t]).to_numpy(), t, None)
            if r:
                ch.append((r[0], "C", r[1]))
    for col in df.columns:
        mt = _TYRE.match(col)
        if mt:
            arr = _num(df[col]).to_numpy()
            if np.nanmax(np.abs(arr)) > 0:
                kind = "Tyre Temp" if mt.group(1).startswith("Temp") else "Tyre Press"
                ch.append((f"{kind} {mt.group(2)} {mt.group(3)}", "C" if kind == "Tyre Temp" else "bar", arr))

    return _motec_csv(
        time_s=time_s,
        channels=ch,
        beacons=[round(float(x), 3) for x in lap_start],
        venue=fn.get("venue", ""),
        driver=fn.get("driver", ""),
        log_date=fn.get("log_date", ""),
        log_time=fn.get("log_time", log_time),
        device="Alfano (export ADA)",
        start_line=None,
    )


# ───────────────────────────────────────────────────────────── zip brut ADA

def _parse_summary(text: str) -> Dict[str, Any]:
    lines = [l for l in text.splitlines() if l.strip()]
    out: Dict[str, Any] = {"lap_ms": [], "egt_max": None}
    if not lines:
        return out
    head = next(csv.reader([lines[0]]))
    if len(head) >= 6:
        out["date"], out["time"] = head[0].strip(), head[1].strip()
        out["track"] = re.sub(r"\s+\d{2}/\d{2}/\d{2}\s*$", "", head[4]).replace("*P*", "").strip()
        out["driver"] = head[5].strip()
        out["device"] = head[11].strip() if len(head) > 11 else "ALFANO"
    if len(lines) > 1:
        cols = next(csv.reader([lines[1]]))
        idx = {c.strip().lower(): i for i, c in enumerate(cols)}
        egts = []
        for l in lines[2:]:
            r = next(csv.reader([l]))
            try:
                out["lap_ms"].append(int(r[idx["time lap"]]))
            except (KeyError, ValueError, IndexError):
                continue
            if "max egt" in idx:
                try:
                    egts.append(float(r[idx["max egt"]]))
                except ValueError:
                    pass
        if egts and max(egts) > 0:
            out["egt_max"] = max(egts) / 10.0
    return out


def _parse_start_line(text: str) -> Optional[Dict[str, float]]:
    vals: Dict[str, float] = {}
    for l in text.splitlines():
        p = [x.strip() for x in l.split(";")]
        if len(p) < 2:
            continue
        key = p[0].lower()
        try:
            v = float(p[1])
        except ValueError:
            continue
        if key.startswith("latitude reference"):
            vals.setdefault("lat", v)
        elif key.startswith("longitude reference"):
            vals.setdefault("lon", v)
        elif key.startswith("orientation reference"):
            vals.setdefault("heading", v)
    if {"lat", "lon"} <= vals.keys() and abs(vals["lat"]) > 0.1:
        vals.setdefault("heading", 0.0)
        return vals
    return None


def alfano_zip_to_motec_csv(content: bytes, interleave_25hz: bool = True) -> bytes:
    try:
        z = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as e:
        raise AlfanoImportError("Zip illisible : réexporte la séance depuis ADA.") from e
    names = z.namelist()

    def read(pred) -> Optional[str]:
        for n in names:
            if pred(_base(n)):
                return z.read(n).decode("utf-8", "ignore")
        return None

    summary = _parse_summary(read(lambda b: b.upper().startswith("SN") and b.lower().endswith(".csv")) or "")
    start_txt = read(lambda b: b.lower().startswith("projection_orthogonale"))
    start_line = _parse_start_line(start_txt) if start_txt else None

    laps: List[Tuple[int, str]] = []
    for n in names:
        mlap = re.match(r"LAP_(\d+)_", _base(n), re.I)
        if mlap and n.lower().endswith(".csv"):
            laps.append((int(mlap.group(1)), n))
    laps.sort()
    if not laps:
        raise AlfanoImportError("Ce zip ne contient pas de tours Alfano (fichiers LAP_…).")

    lap_ms = summary.get("lap_ms") or []
    # Le dernier fichier LAP peut être un tour interrompu (arrêt au stand,
    # drapeau) : sans chrono dans le résumé, il n'est pas dans l'export Excel
    # non plus et fausserait le meilleur tour. On garde les tours chronométrés.
    if lap_ms and len(laps) > len(lap_ms):
        laps = laps[: len(lap_ms)]
    frames, t0 = [], 0.0
    beacons = [0.0]
    for k, (num, name) in enumerate(laps):
        d = pd.read_csv(io.BytesIO(z.read(name)), dtype=float)
        n = len(d)
        if n == 0:
            continue
        dur = lap_ms[k] / 1000.0 if k < len(lap_ms) else n / 10.0
        step = dur / n
        d["__t"] = t0 + np.arange(n) * step
        # Mesures « 25Hz » : prises au milieu de l'intervalle précédent → intercalées.
        if interleave_25hz and {"Speed GPS 25Hz", "Lat. 25Hz", "Lon. 25Hz"} <= set(d.columns):
            mid = d.iloc[1:].copy()
            dlat = mid["Lat. 25Hz"].where(mid["Lat. 25Hz"] <= 32767, mid["Lat. 25Hz"] - 65536)
            dlon = mid["Lon. 25Hz"].where(mid["Lon. 25Hz"] <= 32767, mid["Lon. 25Hz"] - 65536)
            mid["Lat."] = mid["Lat."] + dlat
            mid["Lon."] = mid["Lon."] + dlon
            mid["Speed GPS"] = mid["Speed GPS 25Hz"]
            mid["__t"] = mid["__t"] - step / 2
            for c in ("RPM", "Gf. X", "Gf. Y", "Orientation", "Altitude", "T1", "T2"):
                if c in d:
                    mid[c] = (d[c].iloc[1:].to_numpy() + d[c].iloc[:-1].to_numpy()) / 2
            d = pd.concat([d, mid]).sort_values("__t", kind="stable")
        frames.append(d)
        t0 += dur
        if k < len(lap_ms):
            beacons.append(round(t0, 3))
    df = pd.concat(frames, ignore_index=True)

    time_s = df["__t"].to_numpy()
    lat = df["Lat."].to_numpy() / 1e6
    lon = df["Lon."].to_numpy() / 1e6
    _check(lat, lon, len(beacons) - 1)

    ch: List[Tuple[str, str, np.ndarray]] = [
        ("GPS Latitude", "deg", lat),
        ("GPS Longitude", "deg", lon),
        ("GPS Speed", "km/h", df["Speed GPS"].to_numpy() / 10.0),
    ]
    if "RPM" in df:
        ch.append(("RPM", "rpm", df["RPM"].to_numpy()))
    if "Altitude" in df:
        ch.append(("GPS Altitude", "m", df["Altitude"].to_numpy() / 10.0))
    if "Orientation" in df:
        ch.append(("GPS Heading", "deg", df["Orientation"].to_numpy() / 100.0))
    if "Gf. X" in df:
        ch.append(("GPS LatAcc", "g", (df["Gf. X"].to_numpy() - 1000.0) / 100.0))
    if "Gf. Y" in df:
        ch.append(("GPS LonAcc", "g", -(df["Gf. Y"].to_numpy() - 1000.0) / 100.0))
    if "Speed rear" in df and df["Speed rear"].max() > 0:
        ch.append(("Speed Rear", "km/h", df["Speed rear"].to_numpy() / 10.0))
    for t in ("T1", "T2"):
        if t in df:
            r = _temp_channel(df[t].to_numpy() / 10.0, t, summary.get("egt_max"))
            if r:
                ch.append((r[0], "C", r[1]))

    log_date = ""
    if summary.get("date"):
        try:
            log_date = datetime.strptime(summary["date"], "%d-%m-%Y").strftime("%d/%m/%Y")
        except ValueError:
            log_date = summary["date"]
    return _motec_csv(
        time_s=time_s,
        channels=ch,
        beacons=beacons,
        venue=summary.get("track", ""),
        driver=summary.get("driver", ""),
        log_date=log_date,
        log_time=summary.get("time", ""),
        device=f"{summary.get('device', 'ALFANO')} (zip ADA)".title().replace("Ada", "ADA"),
        start_line=start_line,
    )


def alfano_to_motec_csv(content: bytes, filename: Optional[str] = None) -> bytes:
    if is_alfano_zip(content):
        return alfano_zip_to_motec_csv(content)
    if is_alfano_excel(content):
        return alfano_excel_to_motec_csv(content, filename)
    raise AlfanoImportError("Format Alfano non reconnu.")
