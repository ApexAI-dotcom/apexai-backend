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
    # Grip calibré dans une plage karting réaliste. L'ancien plafond de 1,55 g
    # était atteint sur toutes les séances réelles : c'était lui qui décidait.
    assert 1.0 <= out["mu_calibrated"] <= 2.2
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


# ── Calibration sur le chrono réel ──────────────────────────────────────────
# Le Tour Parfait ne doit répondre qu'à une question : avec CE kart, que
# donnerait une meilleure trajectoire ? Le modèle est donc d'abord recalé pour
# reproduire le chrono démontré sur la trajectoire réellement roulée.

def test_model_reproduces_the_demonstrated_lap(adria_df):
    """Sur la trajectoire roulée, le modèle calibré retrouve le chrono réel."""
    out = build_racing_line(adria_df)
    cal = out["calibration"]
    assert cal["source"] == "meilleur_tour"
    assert cal["reproduced_s"] == pytest.approx(cal["target_s"], abs=0.05)


def test_perfect_lap_never_slower_than_reality(adria_df):
    out = build_racing_line(adria_df)
    assert out["optimal_lap_time_s"] <= out["calibration"]["best_real_s"] + 1e-6


def test_measured_ideal_is_the_reference_when_given(adria_df):
    """Avec l'idéal mesuré (meilleurs secteurs), le Tour Parfait passe dessous."""
    base = build_racing_line(adria_df)
    ideal = round(base["calibration"]["best_real_s"] - 1.0, 3)
    out = build_racing_line(adria_df, target_lap_time_s=ideal)
    assert out["calibration"]["source"] == "ideal_mesure"
    assert out["calibration"]["target_s"] == pytest.approx(ideal)
    assert out["optimal_lap_time_s"] <= ideal + 1e-6


def test_target_slower_than_best_lap_is_ignored(adria_df):
    """Un étalon plus lent que le meilleur tour ne peut pas dégrader l'objectif."""
    base = build_racing_line(adria_df)
    best = base["calibration"]["best_real_s"]
    out = build_racing_line(adria_df, target_lap_time_s=best + 5.0)
    assert out["calibration"]["target_s"] == pytest.approx(best)


def test_gain_comes_from_the_line_only(adria_df):
    """Le gain annoncé reste dans l'ordre de grandeur d'une trajectoire : pas
    les 5 à 7 % d'avant, quand le modèle prêtait au kart un meilleur moteur."""
    out = build_racing_line(adria_df)
    best = out["calibration"]["best_real_s"]
    gain_pct = 100 * (best - out["optimal_lap_time_s"]) / best
    assert 0 <= gain_pct < 4.5


def test_dry_session_is_not_reported_as_contradicting_dry(adria_df):
    """Une séance sèche déclarée sèche ne doit jamais déclencher l'alerte."""
    out = build_racing_line(adria_df)
    assert out["conditions_mismatch"] is False
