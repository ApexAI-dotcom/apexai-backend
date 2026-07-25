"""Tests du module tour idéal (src/analysis/ideal_lap.py)."""
import gzip
import os
import shutil
import tempfile

import numpy as np
import pandas as pd
import pytest

from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter
from src.analysis.geometry import calculate_trajectory_geometry, detect_laps
from src.analysis.ideal_lap import compute_ideal_lap

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


def test_ideal_lap_on_real_multilap(adria_df):
    out = compute_ideal_lap(adria_df)
    assert out["available"] is True
    # Au moins 2 tours propres retenus (out/in-laps et tours lents exclus)
    assert len(out["laps_used"]) >= 2
    # Un tour idéal est toujours ≤ au meilleur tour réel, et le gain est positif borné
    assert out["ideal_lap_time_s"] <= out["best_real_lap_time_s"] + 1e-6
    assert out["potential_gain_s"] >= 0
    assert out["potential_gain_s"] == pytest.approx(
        out["best_real_lap_time_s"] - out["ideal_lap_time_s"], abs=1e-3
    )
    # La somme des temps idéaux par secteur = le tour idéal
    assert sum(s["ideal_time_s"] for s in out["sectors"]) == pytest.approx(
        out["ideal_lap_time_s"], abs=0.05
    )
    # Chrono kart plausible (30–120 s)
    assert 30 < out["ideal_lap_time_s"] < 120


def test_single_lap_returns_unavailable():
    # Un seul tour → pas de tour idéal possible
    df = pd.DataFrame({
        "lap_number": [1] * 10,
        "time": np.linspace(0, 9, 10),
        "cumulative_distance": np.linspace(0, 200, 10),
    })
    out = compute_ideal_lap(df)
    assert out["available"] is False


def test_missing_columns_is_safe():
    df = pd.DataFrame({"speed": [50, 60, 70]})
    out = compute_ideal_lap(df)
    assert out["available"] is False
