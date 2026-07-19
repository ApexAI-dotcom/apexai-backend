#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de non-régression du pipeline d'analyse — fichier d'or : Adria (AiM/MoTeC).

La fixture est une session réelle (A. Giardelli, Adria Karting Raceway)
tronquée à 4 tours et gzippée. À chaque évolution du pipeline (data_loader,
geometry, track_signature), ce test garantit que la signature de piste
mesurée reste stable :
    rapide / horaire / 0 épingle / >=4 virages rapides / ~1180-1260 m.

Lancement :  python -m pytest tests/ -v   (ou python tests/test_track_signature_regression.py)
"""

import gzip
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "adria_4laps.csv.gz")
BEACONS = [82.248, 135.306, 187.523, 238.496, 288.298]


def _run_pipeline(csv_path):
    import numpy as np
    import pandas as pd
    from src.core.data_loader import robust_load_telemetry
    from src.core.signal_processing import apply_savgol_filter
    from src.analysis.geometry import calculate_trajectory_geometry, detect_laps, detect_corners
    from src.analysis.track_signature import compute_track_signature

    result = robust_load_telemetry(csv_path)
    assert result["success"], f"Chargement CSV échoué: {result.get('error')}"
    df = result["data"]
    df.attrs["beacon_markers"] = BEACONS

    df = apply_savgol_filter(df)
    df = calculate_trajectory_geometry(df)
    df = detect_laps(df)

    threshold = None
    if "curvature" in df.columns and "lap_number" in df.columns:
        dfc = df[df["lap_number"] >= 1]
        curv = np.abs(np.nan_to_num(pd.to_numeric(dfc["curvature"], errors="coerce").values, nan=0.0, posinf=0.0, neginf=0.0))
        nz = curv[curv > 1e-6]
        if len(nz):
            threshold = float(np.percentile(nz, 25))

    laps = int(df["lap_number"].nunique()) if "lap_number" in df.columns else 1
    df = detect_corners(df, laps_analyzed=laps, curvature_threshold_override=threshold)
    corners = df.attrs.get("corners", {}).get("corner_details", [])
    return compute_track_signature(corners, df), corners


def test_adria_signature_regression():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "adria_4laps.csv")
        with gzip.open(FIXTURE, "rb") as f_in, open(csv_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        sig, corners = _run_pipeline(csv_path)

    # Signature attendue de la piste d'Adria (mesurée sur cette session)
    assert sig["speed_ratio"] == "rapide", sig
    assert sig["rotation"] == "horaire", sig
    assert sig["hairpins_count"] == 0, sig
    assert sig["fast_corners_count"] >= 4, sig
    assert 9 <= sig["corners_total"] <= 13, sig
    assert 1150 <= sig["track_length_m"] <= 1300, sig
    assert 75 <= sig["avg_apex_speed_kmh"] <= 90, sig

    # Le pipeline détecte des virages confirmés multi-tours
    confirmed = [c for c in corners if c.get("confirmed_in_laps", 0) >= 2]
    assert len(confirmed) >= 8, f"Seulement {len(confirmed)} virages confirmés"


if __name__ == "__main__":
    test_adria_signature_regression()
    print("NON-REGRESSION OK : signature Adria stable")
