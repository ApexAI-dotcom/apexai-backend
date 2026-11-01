#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Météo de la séance, retrouvée sans rien demander au pilote.

Le boîtier écrit la date et l'heure de la séance dans l'en-tête du fichier
(AiM CSV : « Date » / « Time » ; MoTeC et .xrk : « Log Date » / « Log Time »),
et la trace GPS donne le lieu. Avec les deux, on interroge la météo
historique d'Open-Meteo (gratuite, sans clé) pour l'heure de la séance :

- température de l'air, mesurée ;
- état de la piste, déduit de la pluie de l'heure et des trois heures
  d'avant (une piste reste humide après l'averse) ;
- température de la piste, ESTIMÉE (air + gain dû au soleil sur l'asphalte),
  et présentée comme telle.

Ne lève jamais : au moindre doute (pas de date, pas de GPS, réseau coupé),
on renvoie None et l'analyse continue avec ce que le pilote a déclaré,
ou « sec » par défaut, comme avant.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
_HOURLY = "temperature_2m,precipitation,cloud_cover,shortwave_radiation,weather_code"
_TIMEOUT_S = 5.0

_MONTHS_EN = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}

# Codes météo WMO -> libellé court en français.
_WMO = {
    0: "Ciel dégagé", 1: "Plutôt dégagé", 2: "Partiellement nuageux", 3: "Couvert",
    45: "Brouillard", 48: "Brouillard givrant",
    51: "Bruine légère", 53: "Bruine", 55: "Bruine forte",
    61: "Pluie faible", 63: "Pluie", 65: "Pluie forte",
    66: "Pluie verglaçante", 67: "Pluie verglaçante",
    71: "Neige faible", 73: "Neige", 75: "Neige forte",
    80: "Averses", 81: "Averses", 82: "Fortes averses",
    95: "Orage", 96: "Orage et grêle", 99: "Orage et grêle",
}


# ─── Date et heure de la séance ───────────────────────────────────────────────

def _parse_date(raw: str) -> Optional[date]:
    s = (raw or "").strip().strip('"')
    if not s:
        return None
    # « Saturday, May 2, 2026 » (AiM CSV)
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m and m.group(1).lower() in _MONTHS_EN:
        return date(int(m.group(3)), _MONTHS_EN[m.group(1).lower()], int(m.group(2)))
    # « 02/05/2026 », « 2/5/2026 » (jour/mois/année, usage européen de RaceStudio)
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if mo > 12 and d <= 12:  # format américain mois/jour
            d, mo = mo, d
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    # « 2026-05-02 »
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _parse_time(raw: str) -> Optional[Tuple[int, int]]:
    s = (raw or "").strip().strip('"').lower()
    m = re.search(r"(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm)?", s)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if m.group(3) == "pm" and h < 12:
        h += 12
    if m.group(3) == "am" and h == 12:
        h = 0
    if not (0 <= h < 24 and 0 <= mi < 60):
        return None
    return h, mi


def session_datetime(labels: Dict[str, List[str]]) -> Optional[datetime]:
    """Date et heure locales de la séance, lues dans l'en-tête (sans fuseau)."""
    # « Log Date » / « Log Time » d'abord (MoTeC, .xrk converti) : dans ces
    # exports, la première ligne « Time » est celle des canaux, pas l'heure.
    raw_date = (labels.get("log date") or labels.get("date") or [""])[0]
    raw_time = (labels.get("log time") or labels.get("time") or [""])[0]
    d = _parse_date(raw_date)
    if not d:
        return None
    t = _parse_time(raw_time) or (12, 0)
    return datetime(d.year, d.month, d.day, t[0], t[1])


# ─── Déductions ──────────────────────────────────────────────────────────────

def track_condition_from_rain(rain_now_mm: float, rain_before_mm: float) -> str:
    """État de la piste d'après la pluie de l'heure et des 3 heures d'avant."""
    if rain_now_mm >= 1.0:
        return "rain"
    if rain_now_mm >= 0.2:
        return "wet"
    if rain_before_mm >= 1.5:
        return "wet"
    if rain_before_mm >= 0.3:
        return "damp"
    return "dry"


def estimate_track_temperature(air_c: float, radiation_wm2: float) -> float:
    """
    Asphalte au soleil : ≈ air + 2,5 °C par 100 W/m² de rayonnement (plein
    soleil d'été, 800 W/m² : +20 °C), plafonné à +25 °C. À l'ombre ou la
    nuit, la piste reste proche de l'air.
    """
    gain = min(25.0, max(0.0, radiation_wm2) * 0.025)
    return round(air_c + max(1.0, gain), 1)


def _summary(code: Optional[int], air: float, cond: str) -> str:
    label = _WMO.get(int(code)) if code is not None else None
    piste = {"dry": "piste sèche", "damp": "piste humide", "wet": "piste mouillée", "rain": "pluie"}[cond]
    return f"{label or 'Météo'}, {round(air)} °C, {piste}"


# ─── Open-Meteo ──────────────────────────────────────────────────────────────

def _fetch(lat: float, lon: float, day: date) -> Optional[Dict[str, Any]]:
    import httpx

    # La prévision couvre les ~3 derniers mois ; au-delà, l'archive (avec ~5 jours de retard).
    recent = (date.today() - day).days <= 80
    url = _FORECAST_URL if recent else _ARCHIVE_URL
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "hourly": _HOURLY,
        "start_date": (day - timedelta(days=1)).isoformat(),
        "end_date": day.isoformat(),
        "timezone": "auto",
    }
    with httpx.Client(timeout=_TIMEOUT_S) as client:
        r = client.get(url, params=params)
        if r.status_code != 200 and recent:
            r = client.get(_ARCHIVE_URL, params=params)
        if r.status_code != 200:
            return None
        return r.json()


def lookup_session_weather(lat: Optional[float], lon: Optional[float], when: Optional[datetime]) -> Optional[Dict[str, Any]]:
    """Météo à l'heure de la séance, ou None. Ne lève jamais."""
    try:
        if when is None or lat is None or lon is None:
            return None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (abs(lat) < 0.01 and abs(lon) < 0.01):
            return None
        if when.date() > date.today() + timedelta(days=1):
            return None
        data = _fetch(lat, lon, when.date())
        hourly = (data or {}).get("hourly") or {}
        times: List[str] = hourly.get("time") or []
        if not times:
            return None
        key = when.replace(minute=0).strftime("%Y-%m-%dT%H:00")
        if key not in times:
            return None
        i = times.index(key)

        def at(name: str, j: int) -> Optional[float]:
            arr = hourly.get(name) or []
            v = arr[j] if 0 <= j < len(arr) else None
            return float(v) if v is not None else None

        air = at("temperature_2m", i)
        if air is None:
            return None
        rain_now = at("precipitation", i) or 0.0
        rain_before = sum(at("precipitation", j) or 0.0 for j in range(max(0, i - 3), i))
        radiation = at("shortwave_radiation", i) or 0.0
        code = at("weather_code", i)
        cond = track_condition_from_rain(rain_now, rain_before)
        return {
            "source": "open-meteo",
            "at": key,
            "air_temp": round(air, 1),
            "track_temp_estimated": estimate_track_temperature(air, radiation),
            "track_condition": cond,
            "precipitation_mm": round(rain_now, 1),
            "precipitation_3h_before_mm": round(rain_before, 1),
            "cloud_cover_pct": at("cloud_cover", i),
            "radiation_wm2": round(radiation),
            "weather_code": int(code) if code is not None else None,
            "summary": _summary(int(code) if code is not None else None, air, cond),
        }
    except Exception as exc:  # réseau, format inattendu… l'analyse continue sans
        logger.warning("lookup_session_weather: %s", exc)
        return None
