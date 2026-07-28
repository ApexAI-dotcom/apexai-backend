"""
L'analyse de freinage doit être un écosystème qui S'ADAPTE, pas un réglage
calibré sur un fichier.

Le risque, avec un moteur d'analyse, est de le régler jusqu'à ce qu'il donne un
beau résultat sur LE fichier de test, puis de le voir s'effondrer sur le suivant.
Ces tests vérifient les propriétés qui garantissent le contraire :

1. Le résultat ne dépend pas de la fréquence d'échantillonnage de l'appareil.
   Un MyChron à 25 Hz et un Alfano à 5 Hz doivent voir les mêmes freinages.
2. Le résultat ne dépend pas du nombre de tours roulés.
3. Aucun seuil n'est exprimé dans une unité qui dépend de l'appareil.
"""
import gzip
import os
import shutil
import tempfile

import numpy as np
import pandas as pd
import pytest

from src.analysis.braking import analyze_braking
from src.analysis.geometry import calculate_trajectory_geometry, detect_laps, detect_corners
from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "adria_4laps.csv.gz")


def _prepare(decimate: int = 1):
    """Pipeline jusqu'à l'analyse de freinage, avec décimation optionnelle."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        path = tmp.name
    with gzip.open(FIXTURE, "rb") as f_in, open(path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    try:
        df = robust_load_telemetry(path)["data"]
    finally:
        os.unlink(path)

    if decimate > 1:
        # Simule un appareil moins rapide : on ne garde qu'un point sur N.
        df = df.iloc[::decimate].reset_index(drop=True)

    df = apply_savgol_filter(df)
    df = calculate_trajectory_geometry(df)
    df = detect_laps(df)
    laps = int(df["lap_number"].nunique()) if "lap_number" in df.columns else 1
    thr = None
    if "curvature" in df.columns:
        c = np.abs(np.nan_to_num(
            pd.to_numeric(df[df["lap_number"] >= 1]["curvature"], errors="coerce").values))
        nz = c[c > 1e-6]
        if len(nz):
            thr = float(np.percentile(nz, 25))
    df = detect_corners(df, laps_analyzed=laps, curvature_threshold_override=thr)
    details = df.attrs.get("corners", {}).get("corner_details", [])
    return analyze_braking(df, details)


@pytest.fixture(scope="module")
def full_rate():
    return _prepare(1)


@pytest.fixture(scope="module")
def low_rate():
    # Un point sur trois : on descend dans le domaine des boîtiers d'entrée de
    # gamme, ceux qu'on devra bien accepter un jour.
    return _prepare(3)


def test_braking_zones_survive_a_lower_sample_rate(full_rate, low_rate):
    """Les mêmes virages doivent être identifiés comme zones de freinage.

    C'est LA propriété qui rend l'outil utilisable au-delà du fichier de test :
    les seuils sont exprimés en g et en mètres, jamais en écart entre deux
    échantillons successifs. Un critère par échantillon dépendrait de
    l'appareil, et un même pilotage donnerait deux analyses différentes.
    """
    a = set(full_rate["by_corner"])
    b = set(low_rate["by_corner"])
    assert a, "aucune zone de freinage à pleine fréquence"
    assert b, "aucune zone de freinage à fréquence réduite"
    common = a & b
    # On tolère qu'un freinage très court disparaisse quand on divise la
    # résolution par trois ; on n'accepte pas que l'ensemble change.
    assert len(common) >= 0.75 * len(a), (
        f"zones instables : pleine fréquence {sorted(a)}, réduite {sorted(b)}"
    )


def test_braking_points_stay_within_a_kart_length(full_rate, low_rate):
    """Le point de déclenchement ne doit pas se déplacer de façon visible.

    Le pilote va chercher ce repère en piste : un écart de plusieurs dizaines de
    mètres selon l'appareil le rendrait inutilisable.
    """
    diffs = []
    for cid in set(full_rate["by_corner"]) & set(low_rate["by_corner"]):
        d1 = full_rate["by_corner"][cid]["braking_point_distance"]
        d2 = low_rate["by_corner"][cid]["braking_point_distance"]
        diffs.append(abs(d1 - d2))
    if not diffs:
        pytest.skip("aucune zone commune")
    assert max(diffs) <= 15.0, f"repère déplacé de {max(diffs):.1f} m selon l'appareil"
    assert float(np.median(diffs)) <= 8.0


def test_measured_capability_is_stable_across_sample_rates(full_rate, low_rate):
    """La capacité de freinage démontrée décrit le PILOTE, pas le boîtier."""
    c1 = full_rate["capability_g"]
    c2 = low_rate["capability_g"]
    assert abs(c1 - c2) <= 0.15, f"capacité {c1} g vs {c2} g selon l'appareil"


def test_no_threshold_is_expressed_per_sample():
    """Garde-fou de conception : les seuils restent en unités physiques.

    Régression historique : un seuil de « −2 km/h entre deux points » ne
    déclenchait jamais à 25 Hz, où une décélération de 1,2 g ne fait que
    1,8 km/h d'un point au suivant. Le freinage n'était alors JAMAIS détecté.
    """
    from src.analysis import braking

    for name in ("BRAKE_ENTER_G", "BRAKE_EXIT_G", "THROTTLE_ON_G", "MIN_PEAK_G"):
        value = getattr(braking, name)
        assert 0.0 < value < 3.0, f"{name}={value} : hors du domaine du g"
    # Les longueurs sont en mètres, indépendantes de la fréquence.
    assert braking.RESAMPLE_STEP_M > 0
    assert braking.SMOOTH_LENGTH_M > braking.RESAMPLE_STEP_M


def test_flat_corners_are_recognised_not_forced(full_rate):
    """Tous les virages ne se freinent pas : l'outil doit l'admettre.

    Forcer un repère sur un virage pris à plat est le genre de détail qui fait
    dire à un pilote expérimenté que l'analyse est factice.
    """
    braked = set(full_rate["by_corner"])
    assert braked, "aucune zone détectée"
    # Sur un tracé de karting, une partie des virages passe à plat.
    assert len(braked) < 12, "toutes les courbes classées comme freinage"
