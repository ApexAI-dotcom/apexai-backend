"""Tests du moteur de ligne de course idéale (src/analysis/racing_line.py)."""
import gzip
import os
import shutil
import tempfile

import pytest

from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter
from src.analysis.geometry import calculate_trajectory_geometry, detect_laps
from src.analysis.racing_line import build_racing_line

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "adria_4laps.csv.gz")


@pytest.fixture(scope="module")
def adria_df():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        csv_path = tmp.name
    with gzip.open(FIXTURE, "rb") as f_in, open(csv_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    try:
        res = robust_load_telemetry(csv_path)
        assert res["success"], res
        df = res["data"]
        df = apply_savgol_filter(df)
        df = calculate_trajectory_geometry(df)
        df = detect_laps(df)
        yield df
    finally:
        os.unlink(csv_path)


def test_racing_line_is_credible(adria_df):
    out = build_racing_line(adria_df)
    assert out["available"] is True
    # Référence = un vrai tour complet (pas un out/in-lap partiel)
    assert out["track_length_m"] > 800
    # La ligne min-courbure réduit réellement la courbure (objectif atteint)
    assert out["curvature_reduction_pct"] > 10
    # Grip calibré dans une plage karting réaliste
    assert 1.0 <= out["mu_calibrated"] <= 1.55
    # Temps optimal plausible : plus rapide que le meilleur réel, mais pas absurde
    assert 40 < out["optimal_lap_time_s"] < 52
    # La ligne reste bornée dans un couloir de piste réaliste (pas dans le décor)
    assert out["max_lateral_shift_m"] < 8
    # Sortie géométrique cohérente
    assert len(out["lat"]) == len(out["lon"]) == len(out["speed_kmh"]) == out["n_points"]


def test_racing_line_safe_without_gps():
    import pandas as pd
    df = pd.DataFrame({"lap_number": [1, 1, 1], "speed": [40, 50, 60]})
    out = build_racing_line(df)
    assert out["available"] is False
