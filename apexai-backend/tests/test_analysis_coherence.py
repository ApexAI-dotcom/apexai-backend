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


def test_corner_count_does_not_depend_on_session_length():
    """Le circuit ne change pas selon la durée de la session : le nombre de
    virages détectés ne doit pas dépendre du nombre de tours roulés.

    Régression : le seuil de confirmation était `laps // 3`, donc plus le pilote
    roulait, plus le critère devenait sévère — une session de 10 tours trouvait
    moins de virages qu'une session de 4.
    """
    from src.core.data_loader import robust_load_telemetry
    from src.core.signal_processing import apply_savgol_filter
    from src.analysis.geometry import calculate_trajectory_geometry, detect_laps, detect_corners

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        csv_path = tmp.name
    with gzip.open(FIXTURE, "rb") as f_in, open(csv_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    try:
        df = robust_load_telemetry(csv_path)["data"]
        df = apply_savgol_filter(df)
        df = calculate_trajectory_geometry(df)
        df = detect_laps(df)
        counts = set()
        for laps in (2, 4, 9, 20):
            out = detect_corners(df.copy(), laps_analyzed=laps)
            details = out.attrs.get("corners", {}).get("corner_details", [])
            counts.add(len({c["id"] for c in details}))
        assert len(counts) == 1, f"le nombre de virages varie selon la session : {counts}"
    finally:
        os.unlink(csv_path)


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


def test_response_is_json_serializable(analysis):
    """La réponse ne doit contenir aucun type numpy : un int64/float64 casse la
    sérialisation JSON et peut faire disparaître des champs côté application."""
    import json
    import numpy as np

    offenders = []

    def scan(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                scan(v, f"{path}.{k}")
        elif isinstance(obj, (list, tuple)):
            for v in obj[:5]:
                scan(v, f"{path}[]")
        elif isinstance(obj, (np.integer, np.floating, np.bool_, np.ndarray)):
            offenders.append(f"{path} ({type(obj).__name__})")

    scan(analysis)
    assert not offenders, f"types numpy dans la réponse : {offenders}"
    json.dumps(analysis, default=str)


def test_braking_reference_points_are_produced(analysis):
    """Les repères de freinage sont LE repère concret du pilote en piste : sans
    eux, la carte reste abstraite. Ils doivent exister sur la majorité des
    virages et rester à une distance de freinage plausible en karting."""
    corners = analysis["corner_analysis"]
    with_braking = [c for c in corners if c.get("braking_lat") is not None]
    assert len(with_braking) >= len(corners) // 2, (
        f"seulement {len(with_braking)}/{len(corners)} virages ont un repère de freinage"
    )
    for c in with_braking:
        d = float(c["braking_point_distance"])
        assert 0 < d <= 95, f"V{c['corner_id']} : freinage à {d} m de l'apex (implausible)"
        assert c.get("braking_lon") is not None


def test_braking_advice_quotes_only_measured_values(analysis):
    """Tout chiffre cité par un conseil de freinage doit se retrouver tel quel
    dans les données du virage.

    Le conseil peut porter sur l'intensité (g), le temps mort (s), le point
    (m) ou la régularité (± m) : quelle que soit la grandeur mise en avant,
    elle doit être celle que la carte affiche pour ce même virage."""
    import re

    by_id = {c["corner_id"]: c for c in analysis["corner_analysis"]}
    checked = 0
    for a in analysis["coaching_advice"]:
        if a.get("category") != "braking" or a.get("corner") is None:
            continue
        c = by_id[a["corner"]]
        assert c.get("has_braking_zone"), (
            f"conseil de freinage sur V{a['corner']}, qui n'a pas de zone de freinage"
        )
        msg = a["message"]
        allowed = {
            abs(float(c.get("braking_delta") or 0.0)),
            float(c.get("coasting_s") or 0.0),
            float(c.get("braking_peak_g") or 0.0),
            float(c.get("braking_consistency_m") or 0.0),
        }
        numbers = [float(x.replace(",", ".")) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:m|s|g)\b", msg)]
        assert numbers, f"conseil de freinage sans grandeur chiffrée : {msg}"
        for said in numbers:
            assert any(said == pytest.approx(v, abs=0.51) for v in allowed), (
                f"V{a['corner']} : le conseil annonce {said}, valeurs mesurées {sorted(allowed)}"
            )
        checked += 1
    if checked == 0:
        pytest.skip("aucun conseil de freinage sur cette fixture")


def test_driving_phases_are_physical_and_match_the_markers(analysis):
    """Les phases (freinage / accélération / transition) viennent de
    l'accélération longitudinale mesurée, et le repère de freinage doit tomber
    au tout début de la phase de freinage : sinon la bande et la pastille se
    contredisent sur la carte."""
    import numpy as np

    laps = [
        l for l in (analysis.get("plot_data") or {}).get("trajectory_2d", {}).get("laps", [])
        if not l.get("is_synthetic") and l.get("phase") and (l.get("lap_number") or 0) >= 1
    ]
    if not laps:
        pytest.skip("aucun tour avec phases")
    lap = max(laps, key=lambda l: len(l.get("lat") or []))
    assert len(lap["phase"]) == len(lap["lat"]), "phases et points désalignés"

    lat = np.asarray(lap["lat"], dtype=float)
    lon = np.asarray(lap["lon"], dtype=float)
    phases = lap["phase"]
    assert set(phases) <= {"braking", "acceleration", "coasting"}
    # Un tour de karting n'est presque jamais en roue libre.
    coasting = phases.count("coasting") / len(phases)
    assert coasting < 0.45, f"{coasting:.0%} du tour en transition : seuil de phase suspect"

    # La pastille dessinée sur un tour donné doit tomber dans la phase de
    # freinage de CE tour. On compare donc les zones du tour testé, celles-là
    # mêmes que la carte trace, et non l'agrégat calculé sur un autre tour.
    checked = misplaced = 0
    for z in lap.get("braking_zones") or []:
        if z.get("start_lat") is None:
            continue
        checked += 1
        dx = (lon - z["start_lon"]) * np.cos(np.radians(z["start_lat"]))
        dy = lat - z["start_lat"]
        i = int(np.nanargmin(dx * dx + dy * dy))
        window = phases[max(0, i - 2):min(len(phases), i + 5)]
        if "braking" not in window:
            misplaced += 1
    if checked:
        assert misplaced == 0, f"{misplaced}/{checked} repères hors de leur phase de freinage"


def test_braking_marker_is_the_first_point_of_its_band(analysis):
    """La pastille EST le premier point de la bande.

    Régression majeure : tant que le repère et la bande venaient de deux
    calculs distincts, ils dérivaient l'un par rapport à l'autre et la bande
    rouge démarrait bien avant la pastille. Les deux partagent désormais le
    même objet — ce test interdit de les redissocier.
    """
    laps = [l for l in (analysis.get("plot_data") or {}).get("trajectory_2d", {}).get("laps", [])
            if l.get("braking_zones")]
    if not laps:
        pytest.skip("aucune zone de freinage")
    checked = 0
    for lap in laps:
        for z in lap["braking_zones"]:
            assert z["lat"], f"V{z['corner_id']} : bande vide"
            assert z["start_lat"] == z["lat"][0]
            assert z["start_lon"] == z["lon"][0]
            checked += 1
    assert checked >= 5


def test_braking_zones_follow_the_lap_order(analysis):
    """Sur un tour, les zones de freinage se succèdent dans l'ordre des virages.

    Régression : le repère du virage 8 pouvait se retrouver AVANT le virage 7
    sur la carte, un ordre physiquement impossible.
    """
    import numpy as np

    laps = [l for l in (analysis.get("plot_data") or {}).get("trajectory_2d", {}).get("laps", [])
            if l.get("braking_zones") and l.get("lat")]
    if not laps:
        pytest.skip("aucune zone de freinage")
    for lap in laps:
        lat = np.asarray(lap["lat"], dtype=float)
        lon = np.asarray(lap["lon"], dtype=float)
        positions = []
        for z in sorted(lap["braking_zones"], key=lambda x: x["corner_id"]):
            dx = (lon - z["start_lon"]) * np.cos(np.radians(z["start_lat"]))
            dy = lat - z["start_lat"]
            positions.append(int(np.nanargmin(dx * dx + dy * dy)))
        # Un seul décrochage toléré : la zone du premier virage peut commencer
        # avant la ligne, donc en fin de trace.
        breaks = sum(1 for a, b in zip(positions, positions[1:]) if b <= a)
        assert breaks <= 1, (
            f"tour {lap.get('lap_number')} : ordre des zones incohérent {positions}"
        )


def test_flat_corners_have_no_braking_marker(analysis):
    """Un virage pris à plat ne doit afficher aucun repère de freinage.

    Inventer une pastille sur un virage rapide est ce qui fait dire à un pilote
    expérimenté que l'outil est factice.
    """
    for c in analysis["corner_analysis"]:
        if c.get("has_braking_zone"):
            continue
        assert c.get("braking_lat") is None and c.get("braking_lon") is None
        assert float(c.get("braking_point_distance") or 0.0) == 0.0
    advised = {a["corner"] for a in analysis["coaching_advice"]
               if a.get("category") == "braking" and a.get("corner")}
    flat = {c["corner_id"] for c in analysis["corner_analysis"] if not c.get("has_braking_zone")}
    assert not (advised & flat), f"conseils de freinage sur des virages sans freinage : {advised & flat}"


def test_braking_intensity_is_physically_possible(analysis):
    """Les décélérations annoncées restent dans le domaine du karting.

    Un kart freine entre 0,3 g et 1,6 g. Au-delà, c'est un artefact de calcul
    et non une performance.
    """
    for c in analysis["corner_analysis"]:
        if not c.get("has_braking_zone"):
            continue
        peak = float(c.get("braking_peak_g") or 0.0)
        assert 0.3 <= peak <= 1.6, f"V{c['corner_id']} : crête de {peak} g"
        assert float(c.get("braking_avg_g") or 0.0) <= peak + 1e-6
        assert 0.0 <= float(c.get("coasting_s") or 0.0) <= 5.0
        assert int(c.get("laps") or 1) >= 2, (
            f"V{c['corner_id']} : zone de freinage vue sur un seul tour"
        )


def test_braking_markers_follow_the_track_order(analysis):
    """Un repère de freinage appartient au segment compris entre le virage
    PRÉCÉDENT et le sien.

    Régression : la fenêtre de recherche (90 m en amont de l'apex) pouvait
    traverser le virage amont, si bien que le repère du virage 8 se retrouvait
    AVANT le virage 7 sur la carte — un ordre physiquement impossible.
    """
    import numpy as np

    laps = [
        l for l in (analysis.get("plot_data") or {}).get("trajectory_2d", {}).get("laps", [])
        if not l.get("is_synthetic") and (l.get("lap_number") or 0) >= 1 and l.get("lat")
    ]
    if not laps:
        pytest.skip("aucun tour exploitable")
    lap = max(laps, key=lambda l: len(l["lat"]))
    lat = np.asarray(lap["lat"], dtype=float)
    lon = np.asarray(lap["lon"], dtype=float)

    def index_of(la, lo):
        dx = (lon - lo) * np.cos(np.radians(la))
        dy = lat - la
        return int(np.nanargmin(dx * dx + dy * dy))

    previous_apex = None
    for c in analysis["corner_analysis"]:
        apex_i = index_of(c["apex_lat"], c["apex_lon"])
        if c.get("braking_lat") is not None:
            brake_i = index_of(c["braking_lat"], c["braking_lon"])
            assert brake_i <= apex_i, (
                f"V{c['corner_id']} : repère de freinage APRÈS son propre apex"
            )
            if previous_apex is not None:
                assert brake_i >= previous_apex, (
                    f"V{c['corner_id']} : repère de freinage situé avant le virage précédent"
                )
        previous_apex = apex_i


def test_racing_line_preserves_every_corner(analysis):
    """Le Tour Parfait IA ne supprime jamais un virage (pas de chicane coupée)."""
    rl = analysis.get("racing_line") or {}
    if not rl.get("available"):
        pytest.skip("ligne de course indisponible sur cette fixture")
    assert rl["corners_preserved"] == rl["corners_total"]
    assert rl["track_width_m"] == TRACK_WIDTH_M
    assert rl.get("track_edges"), "bords de piste absents (ruban non traçable)"


def test_score_breakdown_sums_to_the_displayed_score(analysis):
    """Le détail du score doit totaliser le score affiché.

    Régression : le bonus « conditions difficiles » entrait dans le score global
    mais était absent du modèle de réponse. Le rapport affichait 76/100 avec un
    détail totalisant 71,2 — de quoi faire douter de tous les autres chiffres.
    """
    ps = analysis["performance_score"]
    bd = ps["breakdown"]
    total = sum(float(v) for v in bd.values() if v is not None)
    assert total == pytest.approx(float(ps["overall_score"]), abs=0.15), (
        f"détail {total:.1f} ≠ score affiché {ps['overall_score']}"
    )


def test_information_notes_never_crowd_out_real_advice(analysis):
    """Les encarts d'information ne consomment pas le quota de conseils.

    Régression : trois encarts (conditions + température) suffisaient à faire
    tomber la liste tronquée à deux conseils réellement exploitables.
    """
    real = [a for a in analysis["coaching_advice"] if a.get("category") != "info"]
    assert len(real) >= 3, f"seulement {len(real)} conseils exploitables"


def test_trail_braking_is_a_discriminating_measure(analysis):
    """Le trail braking doit distinguer les virages, pas afficher 100 % partout.

    Régression : le seuil était absolu (0,4 g latéral), atteint à 100 km/h avec
    un rayon de 200 m — donc sur presque toute la piste. Tous les virages
    affichaient « trail braking 100 % », ce qui ne voulait plus rien dire.
    """
    ratios = [
        float(c["trail_braking_ratio"])
        for c in analysis["corner_analysis"]
        if c.get("has_braking_zone") and c.get("trail_braking_ratio") is not None
    ]
    if len(ratios) < 3:
        pytest.skip("pas assez de zones de freinage")
    assert all(0.0 <= r <= 1.0 for r in ratios)
    assert len(set(round(r, 1) for r in ratios)) > 1, f"valeur unique partout : {ratios}"
    assert sum(1 for r in ratios if r >= 0.99) < len(ratios), "100 % sur tous les virages"


def test_no_long_unlabelled_stretch_in_driving_phases(analysis):
    """Aucune longue portion du tour ne doit rester sans phase identifiée.

    Régression : tout ce qui précédait le premier freinage du tour — la ligne
    droite de départ, pleins gaz — restait étiqueté « ni frein ni gaz » et
    s'affichait en gris sur la carte, sans explication.
    """
    laps = [
        l for l in (analysis.get("plot_data") or {}).get("trajectory_2d", {}).get("laps", [])
        if not l.get("is_synthetic") and l.get("phase") and (l.get("lap_number") or 0) >= 1
    ]
    if not laps:
        pytest.skip("aucun tour avec phases")
    lap = max(laps, key=lambda l: len(l.get("phase") or []))
    phases = lap["phase"]
    longest = current = 0
    for p in phases:
        current = current + 1 if p == "coasting" else 0
        longest = max(longest, current)
    assert longest < len(phases) * 0.2, (
        f"{longest}/{len(phases)} points consécutifs sans phase identifiée"
    )
