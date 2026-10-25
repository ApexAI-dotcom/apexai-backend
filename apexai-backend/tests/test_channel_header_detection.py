"""
Où commencent les données d'un export ?

Le chargeur sautait 14 lignes dès qu'il lisait « aim » dans l'en-tête. Juste
pour un export RaceStudio complet ; faux dès que l'en-tête change de longueur.
Une séance sans passage sur la ligne n'a ni « Beacon Markers » ni « Segment
Times » : le saut fixe avalait alors les noms de canaux et les premières
mesures. La ligne des canaux est maintenant cherchée par son contenu.

Données entièrement synthétiques : aucun fichier de pilote dans le dépôt.
"""
import math

import pytest

from src.core.data_loader import _detect_format, _find_channel_header_row, robust_load_telemetry

N_ROWS = 400


def _data_rows():
    rows = []
    for k in range(N_ROWS):
        a = 2 * math.pi * k / 200.0
        lat = 45.0 + 0.0008 * math.sin(a)
        lon = 5.0 + 0.0012 * math.cos(a)
        rows.append(f"{k * 0.05:.3f},{60 + 20 * math.sin(a):.2f},{lat:.7f},{lon:.7f}")
    return rows


def _write(tmp_path, header, name):
    lines = header + [
        '"Time","GPS Speed","GPS Latitude","GPS Longitude"',
        '"s","km/h","deg","deg"',
    ] + _data_rows()
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


AIM_FULL = [
    '"Format","AiM CSV File"', '"Session","CircuitTest"', '"Vehicle","KART"',
    '"Racer","PILOTE"', '"Championship",""', '"Comment",""',
    '"Date","Sunday, January 4, 2026"', '"Time","9:00 AM"', '"Sample Rate","20"',
    '"Duration","20.0"', '"Segment","Session"', '"Beacon Markers","10.0","20.0"',
    '"Segment Times","0:10.000","0:10.000"', "",
]
# Séance sans passage sur la ligne : deux lignes d'en-tête en moins.
AIM_NO_BEACONS = [l for l in AIM_FULL if not l.startswith(('"Beacon', '"Segment Times'))]


def test_full_racestudio_export_unchanged(tmp_path):
    """Le cas courant donne exactement l'ancien résultat : 14 lignes d'en-tête."""
    path = _write(tmp_path, AIM_FULL, "full.csv")
    assert _find_channel_header_row(path) == 14
    assert _detect_format(path) == 14


def test_shorter_header_is_found(tmp_path):
    path = _write(tmp_path, AIM_NO_BEACONS, "short.csv")
    assert _detect_format(path) == 12


def test_shorter_header_loads_every_sample(tmp_path):
    """Les premières mesures ne doivent plus disparaître avec l'en-tête."""
    res = robust_load_telemetry(_write(tmp_path, AIM_NO_BEACONS, "short.csv"))
    assert res["success"], res.get("error")
    df = res["data"]
    assert {"time", "latitude", "longitude"} <= set(df.columns)
    assert float(df["time"].min()) == pytest.approx(0.0)


def test_metadata_time_row_is_not_taken_for_channels(tmp_path):
    """« Time », « 9:00 AM » est une métadonnée, pas la ligne des canaux."""
    path = _write(tmp_path, AIM_FULL, "full.csv")
    assert _find_channel_header_row(path) != 7


def test_plain_csv_starts_at_first_line(tmp_path):
    path = _write(tmp_path, [], "plain.csv")
    assert _detect_format(path) == 0


def test_semicolon_csv_is_found(tmp_path):
    p = tmp_path / "semi.csv"
    p.write_text("Info;Export\n\nTime;Speed;Lat;Lon\n0;10;45;5\n", encoding="utf-8")
    assert _find_channel_header_row(str(p)) == 2


def test_file_without_gps_columns_falls_back(tmp_path):
    p = tmp_path / "nogps.csv"
    p.write_text("Time,RPM,Water\n0,9000,50\n", encoding="utf-8")
    assert _find_channel_header_row(str(p)) is None
