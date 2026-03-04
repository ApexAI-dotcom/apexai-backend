"""
Test de régression : vérifier que detect_corners() retourne le même nombre de virages
quels que soient les tours sélectionnés, grâce à la calibration sur track complet
(calibrate_track_geometry + expected_corners).
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import pytest
except ImportError:
    pytest = None

from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter
from src.analysis.geometry import (
    calculate_trajectory_geometry,
    calibrate_track_geometry,
    detect_laps,
    detect_corners,
)


def _filter_laps_with_buffer(df, lap_filter):
    """Copie minimale de la logique services._filter_laps_with_buffer pour le test."""
    if not lap_filter or "lap_number" not in df.columns:
        return df[df["lap_number"].isin(lap_filter)].reset_index(drop=True) if lap_filter else df
    import numpy as np
    BUFFER_BEFORE_AFTER = 75
    BUFFER_BETWEEN_GROUPS = 50
    n = len(df)
    laps_sorted = sorted(set(lap_filter))
    positions_to_keep = set()
    prev_end = -1
    for i, lap in enumerate(laps_sorted):
        pos = np.where(df["lap_number"].values == lap)[0]
        if len(pos) == 0:
            continue
        mi, ma = int(pos.min()), int(pos.max())
        if i == 0:
            start_buf = max(0, mi - BUFFER_BEFORE_AFTER)
            end_buf = ma + BUFFER_BETWEEN_GROUPS if len(laps_sorted) > 1 else min(n - 1, ma + BUFFER_BEFORE_AFTER)
            positions_to_keep.update(range(start_buf, end_buf + 1))
        elif i == len(laps_sorted) - 1:
            if lap - laps_sorted[i - 1] > 1:
                gap_start = max(0, prev_end + 1)
                gap_end = min(n - 1, prev_end + BUFFER_BETWEEN_GROUPS)
                positions_to_keep.update(range(gap_start, gap_end + 1))
                positions_to_keep.update(range(max(0, mi - BUFFER_BETWEEN_GROUPS), mi))
            end_buf = min(n - 1, ma + BUFFER_BEFORE_AFTER)
            positions_to_keep.update(range(max(0, mi - BUFFER_BETWEEN_GROUPS), end_buf + 1))
        else:
            if lap - laps_sorted[i - 1] > 1:
                positions_to_keep.update(range(max(0, prev_end + 1), min(n, prev_end + BUFFER_BETWEEN_GROUPS + 1)))
                positions_to_keep.update(range(max(0, mi - BUFFER_BETWEEN_GROUPS), mi))
            positions_to_keep.update(range(mi, ma + 1))
        prev_end = ma
    pos_sorted = sorted(positions_to_keep)
    if not pos_sorted:
        return df[df["lap_number"].isin(lap_filter)].reset_index(drop=True)
    return df.iloc[pos_sorted].reset_index(drop=True)


def _get_test_csv_path():
    return os.environ.get("APEXAI_TEST_CSV") or (project_root / "temp" / "test_valid.csv")


def _load_full_df_and_params():
    """Charge le CSV, géométrie, laps, calibration. Retourne (df, params) ou (None, None) si skip."""
    path = _get_test_csv_path()
    if not path or not Path(path).exists():
        return None, None
    result = robust_load_telemetry(str(path))
    if not result.get("success"):
        return None, None
    df = result["data"]
    df = apply_savgol_filter(df)
    df = calculate_trajectory_geometry(df)
    df = detect_laps(df)
    if "lap_number" not in df.columns or df["lap_number"].nunique() < 2:
        return None, None
    global_params = calibrate_track_geometry(df)
    return df, global_params


def _fixture_full_df_and_params():
    if pytest is None:
        return _load_full_df_and_params()
    path = _get_test_csv_path()
    if not path or not Path(path).exists():
        pytest.skip(f"Fichier test absent: {path}. Définir APEXAI_TEST_CSV pour exécuter.")
    result = robust_load_telemetry(str(path))
    if not result.get("success"):
        pytest.skip(f"Chargement échoué: {result.get('error', 'Unknown')}")
    df = result["data"]
    df = apply_savgol_filter(df)
    df = calculate_trajectory_geometry(df)
    df = detect_laps(df)
    if "lap_number" not in df.columns or df["lap_number"].nunique() < 2:
        pytest.skip("Fichier test n'a pas assez de tours (lap_number). Utiliser un CSV avec beacons.")
    global_params = calibrate_track_geometry(df)
    return df, global_params


if pytest is not None:
    @pytest.fixture(scope="module")
    def full_df_and_params():
        return _fixture_full_df_and_params()


def test_corner_consistency_across_lap_selections(full_df_and_params=None):
    """Pour plusieurs sélections de tours, le nombre de virages doit être identique (calibration globale)."""
    if full_df_and_params is None and pytest is not None:
        full_df_and_params = _fixture_full_df_and_params()
    elif full_df_and_params is None:
        full_df_and_params = _load_full_df_and_params()
    df_full, global_params = full_df_and_params
    if df_full is None:
        if pytest is not None:
            pytest.skip("Fichier test absent ou sans tours. Définir APEXAI_TEST_CSV.")
        return
    available_laps = sorted([int(x) for x in df_full["lap_number"].dropna().unique() if x >= 1])
    if len(available_laps) < 2:
        if pytest is not None:
            pytest.skip("Moins de 2 tours disponibles pour tester plusieurs combinaisons.")
        return
    # Référence : détection sur track complet
    df_ref = detect_corners(
        df_full.copy(),
        laps_analyzed=len(available_laps),
        global_params=global_params,
    )
    ref_count = len(df_ref.attrs.get("corners", {}).get("corner_details", []))
    assert ref_count >= 1, "Track complet doit donner au moins 1 virage"
    # Combinaisons de tours (au plus 3 pour garder le test rapide)
    test_cases = [
        available_laps[: min(3, len(available_laps))],
        available_laps[-min(3, len(available_laps)) :] if len(available_laps) >= 3 else available_laps,
    ]
    if len(available_laps) >= 4:
        mid = len(available_laps) // 2
        test_cases.append(available_laps[mid : mid + 2])
    for lap_list in test_cases:
        if not lap_list:
            continue
        df_subset = _filter_laps_with_buffer(df_full.copy(), lap_list)
        if len(df_subset) < 50:
            continue
        params_with_expected = {**global_params, "expected_corners": ref_count}
        df_corners = detect_corners(
            df_subset,
            laps_analyzed=len(lap_list),
            global_params=params_with_expected,
        )
        count = len(df_corners.attrs.get("corners", {}).get("corner_details", []))
        assert count == ref_count, (
            f"Tours {lap_list}: {count} corners au lieu de {ref_count}. "
            "La calibration globale (expected_corners) doit stabiliser le comptage."
        )


def test_calibrate_track_geometry_returns_curvature_threshold(full_df_and_params=None):
    """calibrate_track_geometry doit retourner curvature_threshold et track_length_m."""
    if full_df_and_params is None and pytest is not None:
        full_df_and_params = _fixture_full_df_and_params()
    elif full_df_and_params is None:
        full_df_and_params = _load_full_df_and_params()
    if full_df_and_params[0] is None:
        if pytest is not None:
            pytest.skip("Fichier test absent.")
        return
    _, global_params = full_df_and_params
    assert "curvature_threshold" in global_params
    assert "track_length_m" in global_params
    # curvature_threshold peut être None si pas de courbure
    assert global_params.get("track_length_m") >= 0


if __name__ == "__main__":
    print("Run corner consistency tests (sans pytest)...")
    df_and_p = _load_full_df_and_params()
    if df_and_p[0] is None:
        print("Skip: pas de fichier test avec plusieurs tours (APEXAI_TEST_CSV ou temp/test_valid.csv).")
    else:
        test_calibrate_track_geometry_returns_curvature_threshold(df_and_p)
        print("test_calibrate: OK")
        test_corner_consistency_across_lap_selections(df_and_p)
        print("test_corner_consistency: OK")
    print("Done.")
