#!/usr/bin/env python3
"""Météo de la séance : lecture de la date, déductions, appel Open-Meteo simulé."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.analysis import weather as W  # noqa: E402


def test_session_datetime_aim_csv():
    labels = {"date": ["Saturday, May 2, 2026"], "time": ["10:17 AM"]}
    assert W.session_datetime(labels) == datetime(2026, 5, 2, 10, 17)


def test_session_datetime_motec_prefers_log_time():
    # La ligne « Time » des canaux ne doit pas être prise pour l'heure.
    labels = {"log date": ["02/05/2026"], "log time": ["14:05:31"], "time": ["GPS Speed", "RPM"]}
    assert W.session_datetime(labels) == datetime(2026, 5, 2, 14, 5)


def test_session_datetime_pm_and_missing():
    assert W.session_datetime({"date": ["Sunday, November 1, 2026"], "time": ["3:40 PM"]}) == datetime(2026, 11, 1, 15, 40)
    assert W.session_datetime({}) is None


def test_track_condition_from_rain():
    assert W.track_condition_from_rain(0, 0) == "dry"
    assert W.track_condition_from_rain(0, 0.5) == "damp"
    assert W.track_condition_from_rain(0, 2.0) == "wet"
    assert W.track_condition_from_rain(0.4, 0) == "wet"
    assert W.track_condition_from_rain(2.0, 0) == "rain"


def test_track_temperature_estimate():
    assert W.estimate_track_temperature(20, 800) == 40.0
    assert W.estimate_track_temperature(10, 0) == 11.0
    assert W.estimate_track_temperature(30, 2000) == 55.0


def test_lookup_uses_hour_of_session(monkeypatch):
    hours = [f"2026-05-0{d}T{h:02d}:00" for d in (1, 2) for h in range(24)]
    fake = {"hourly": {
        "time": hours,
        "temperature_2m": [15.0] * 48,
        "precipitation": [0.0] * 32 + [0.3, 0.4, 0.0] + [0.0] * 13,  # pluie à 8 h et 9 h le 2
        "shortwave_radiation": [400.0] * 48,
        "cloud_cover": [80.0] * 48,
        "weather_code": [61] * 48,
    }}
    monkeypatch.setattr(W, "_fetch", lambda lat, lon, day: fake)
    w = W.lookup_session_weather(46.3, 3.36, datetime(2026, 5, 2, 10, 17))
    assert w["at"] == "2026-05-02T10:00"
    assert w["air_temp"] == 15.0
    assert w["track_condition"] == "damp"  # 0,7 mm dans les 3 h d'avant
    assert w["track_temp_estimated"] == 25.0


def test_lookup_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("réseau coupé")
    monkeypatch.setattr(W, "_fetch", boom)
    assert W.lookup_session_weather(46.3, 3.36, datetime(2026, 5, 2, 10, 0)) is None
    assert W.lookup_session_weather(None, None, datetime(2026, 5, 2, 10, 0)) is None
    assert W.lookup_session_weather(46.3, 3.36, None) is None
