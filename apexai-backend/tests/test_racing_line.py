"""Tests du moteur de ligne de course idéale (src/analysis/racing_line.py)."""
import gzip
import os
import shutil
import tempfile

import pytest

from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter
from src.analysis.geometry import calculate_trajectory_geometry, detect_laps, detect_corners
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
        # Même chaîne que le pipeline réel : la ligne idéale doit s'appuyer sur
        # les virages détectés par l'application (numérotation de la carte).
        df = detect_corners(df)
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


def test_racing_line_never_deletes_a_corner(adria_df):
    """GARANTIE MÉTIER : la ligne idéale ne doit jamais gommer un virage
    (sinon elle couperait la piste — cas de la chicane raccourcie)."""
    out = build_racing_line(adria_df)
    assert out["available"] is True
    assert out["corners_total"] >= 5, "détection de virages anormalement faible"
    assert out["corners_preserved"] == out["corners_total"], (
        f"{out['corners_total'] - out['corners_preserved']} virage(s) supprimé(s) "
        "par l'optimisation"
    )


def test_corners_match_the_app_numbering(adria_df):
    """Le nombre de virages de la ligne idéale doit être CELUI de l'analyse
    (carte + graphiques), pas un décompte interne différent."""
    out = build_racing_line(adria_df)
    assert out["corners_source"] == "virages détectés par l'analyse"
    # Les virages sont relevés sur toute la session : au moins ceux du tour de
    # référence, au plus ceux détectés sur l'ensemble des tours. Dans le pipeline
    # (où les virages sont renumérotés 1..N) les deux bornes coïncident et le
    # décompte est exactement celui affiché sur la carte.
    ref = adria_df[adria_df["lap_number"] == out["reference_lap"]]
    n_ref = int(ref["corner_id"].dropna().nunique())
    n_session = int(adria_df["corner_id"].dropna().nunique())
    assert n_ref <= out["corners_total"] <= n_session
    # Et surtout : tous sont préservés.
    assert out["corners_preserved"] == out["corners_total"]


def test_ideal_line_stays_close_in_tight_corners(adria_df):
    """Dans un virage serré le pilote frôle déjà la corde : la ligne idéale ne
    doit pas s'en écarter au point de redresser/couper le virage."""
    out = build_racing_line(adria_df)
    assert out["max_lateral_shift_m"] <= 5.0


def test_track_width_is_regulation_based(adria_df):
    """La largeur de piste vient de la réglementation karting (généralisable à
    tous les circuits), pas d'un calage sur un tracé particulier."""
    out = build_racing_line(adria_df)
    assert out["track_width_m"] == 8.0
    assert "CIK-FIA" in out["track_width_source"]
    edges = out["track_edges"]
    assert len(edges["left"]["lat"]) == len(edges["right"]["lat"]) == out["n_points"]


def test_racing_line_safe_without_gps():
    import pandas as pd
    df = pd.DataFrame({"lap_number": [1, 1, 1], "speed": [40, 50, 60]})
    out = build_racing_line(df)
    assert out["available"] is False
