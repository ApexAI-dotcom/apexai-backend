"""
Garanties de cohérence de l'analyse — le pilote doit pouvoir faire confiance
à ce qu'il lit.

Ces tests protègent des régressions les plus destructrices de crédibilité :
un conseil qui cite un virage absent de la carte, une numérotation qui diverge
entre la carte et les graphiques, ou des chiffres physiquement impossibles.
"""
import gzip
import os
import shutil
import tempfile
from datetime import datetime

import pytest

from src.api.services import _run_analysis_pipeline_sync

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "adria_4laps.csv.gz")
# Largeur de piste karting de compétition (CIK-FIA : minimum 8 m)
TRACK_WIDTH_M = 8.0


@pytest.fixture(scope="module")
def analysis():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        csv_path = tmp.name
    with gzip.open(FIXTURE, "rb") as f_in, open(csv_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    try:
        yield _run_analysis_pipeline_sync(
            csv_path, [], "test-coherence", datetime.now(),
            track_condition="dry", track_temperature=24.0,
        )
    finally:
        os.unlink(csv_path)


def _map_corner_ids(analysis):
    corners = (analysis.get("plot_data") or {}).get("trajectory_2d", {}).get("corners", [])
    return {int(c["label"].lstrip("V")) for c in corners if c.get("label")}


def test_corner_numbering_is_contiguous(analysis):
    """Les virages sont numérotés 1..N sans trou : le pilote compte sur la carte."""
    ids = [c["corner_id"] for c in analysis["corner_analysis"]]
    assert ids == list(range(1, len(ids) + 1))
    assert analysis["corners_detected"] == len(ids)


def test_map_shows_exactly_the_analysed_corners(analysis):
    """Carte et analyse affichent le MÊME ensemble de virages."""
    ids = {c["corner_id"] for c in analysis["corner_analysis"]}
    assert _map_corner_ids(analysis) == ids


def test_every_advised_corner_exists_on_the_map(analysis):
    """Un conseil ne peut jamais citer un virage introuvable sur la carte."""
    on_map = _map_corner_ids(analysis)
    advised = [a["corner"] for a in analysis["coaching_advice"] if a.get("corner") is not None]
    assert advised, "aucun conseil ciblé généré"
    missing = [c for c in advised if c not in on_map]
    assert not missing, f"conseils pointant des virages absents de la carte : {missing}"


def test_apex_errors_are_physically_possible(analysis):
    """Une erreur d'apex ne peut pas dépasser la demi-largeur de piste."""
    for c in analysis["corner_analysis"]:
        err = float(c.get("apex_distance_error") or 0.0)
        assert 0 <= err <= TRACK_WIDTH_M / 2.0, f"V{c['corner_id']} : apex error {err} m"


def test_advice_impacts_match_measured_losses(analysis):
    """Le gain annoncé par un conseil est la perte RÉELLEMENT mesurée du virage,
    jamais une valeur inventée ni gonflée par le nombre de tours."""
    losses = {c["corner_id"]: float(c.get("time_lost") or 0.0)
              for c in analysis["corner_analysis"]}
    for a in analysis["coaching_advice"]:
        cid = a.get("corner")
        if cid is None:
            continue
        assert a["impact_seconds"] == pytest.approx(losses[cid], abs=1e-3)


def test_best_lap_time_excludes_partial_laps(analysis):
    """Le « meilleur tour » ne peut pas être un tour de rentrée tronqué."""
    best = analysis["best_lap_time"]
    assert best > 20, f"meilleur tour irréaliste ({best}s) — tour partiel retenu ?"
    ideal = analysis.get("ideal_lap") or {}
    if ideal.get("available"):
        assert ideal["best_real_lap_time_s"] == pytest.approx(best, abs=0.01)


def test_ideal_lap_is_reachable(analysis):
    """Le tour idéal est composé de portions réellement réalisées : il ne peut
    pas être plus rapide que la somme des meilleurs secteurs."""
    ideal = analysis.get("ideal_lap") or {}
    if not ideal.get("available"):
        pytest.skip("tour idéal indisponible sur cette fixture")
    assert ideal["ideal_lap_time_s"] <= ideal["best_real_lap_time_s"]
    assert ideal["potential_gain_s"] >= 0
    assert ideal["laps_used"], "aucun tour représentatif retenu"


def test_no_unmeasured_seconds_are_ever_claimed(analysis):
    """Sans plusieurs tours exploitables, on ne peut pas MESURER un temps perdu.
    Dans ce cas l'analyse doit afficher 0 et non une approximation déguisée."""
    measured = bool((analysis.get("ideal_lap") or {}).get("available"))
    for c in analysis["corner_analysis"]:
        source = c.get("time_lost_source")
        assert source in ("measured", "unavailable"), f"source inconnue : {source}"
        if not measured:
            assert float(c.get("time_lost") or 0.0) == 0.0


def test_braking_distances_are_physically_sane(analysis):
    """Les distances de freinage annoncées doivent rester dans le domaine du
    possible : un écart de 78 m au point de freinage n'est pas un défaut de
    pilotage mais un défaut de calcul."""
    for c in analysis["corner_analysis"]:
        dist = float(c.get("braking_point_distance") or 0.0)
        delta = float(c.get("braking_delta") or 0.0)
        assert 0 <= dist <= 300, f"V{c['corner_id']} : freinage à {dist} m de l'apex"
        assert abs(delta) <= 60, f"V{c['corner_id']} : écart de freinage {delta} m"


def test_racing_line_preserves_every_corner(analysis):
    """Le Tour Parfait IA ne supprime jamais un virage (pas de chicane coupée)."""
    rl = analysis.get("racing_line") or {}
    if not rl.get("available"):
        pytest.skip("ligne de course indisponible sur cette fixture")
    assert rl["corners_preserved"] == rl["corners_total"]
    assert rl["track_width_m"] == TRACK_WIDTH_M
    assert rl.get("track_edges"), "bords de piste absents (ruban non traçable)"
