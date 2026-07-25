#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — End-to-end smoke test of the analysis pipeline.

Synthetic 3-lap session on a circular track, pushed through the whole chain:
geometry → laps → corners → per-corner performance → score → coaching.

Assertions stay structural on purpose: this file guards the plumbing between
the modules (shapes, keys, ranges), not the tuning of any single algorithm.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.analysis.geometry import calculate_trajectory_geometry, detect_corners, detect_laps
from src.analysis.performance_metrics import analyze_corner_performance
from src.analysis.scoring import calculate_performance_score
from src.analysis.coaching import generate_coaching_advice

LAPS_ANALYZED = 3


@pytest.fixture(scope="module")
def session_df():
    """3 laps around a 50 m circle, speed oscillating between 50 and 70."""
    n_pts = 3000
    t = np.linspace(0, 300, n_pts)
    radius = 50
    # Slightly shifted laps so trajectory consistency has something to chew on
    lap_offsets = np.repeat(np.array([0, 0.0001, 0.0002]), 1000)
    lat = 45.0 + ((radius / 111000) * np.sin(t / 10)) + lap_offsets
    lon = 5.0 + ((radius / (111000 * np.cos(np.radians(45.0)))) * np.cos(t / 10))

    df = pd.DataFrame({
        "time": t,
        "latitude_smooth": lat,
        "longitude_smooth": lon,
        "speed": np.full(n_pts, 60.0) + np.sin(t / 5) * 10,
    })

    df = calculate_trajectory_geometry(df)
    df = detect_laps(df)
    df["lateral_g"] = np.sin(t / 3) * 1.5  # pseudo lateral G
    df = detect_corners(df)
    return df


@pytest.fixture(scope="module")
def corner_details(session_df):
    assert "corners" in session_df.attrs, "detect_corners must attach df.attrs['corners']"
    details = session_df.attrs["corners"].get("corner_details")
    assert details, "Pipeline detected no corner on the synthetic circuit"
    return details


@pytest.fixture(scope="module")
def corner_analysis(session_df, corner_details):
    """Per-corner metrics, merged back into the corner payload as in production."""
    analyses = []
    for corner in corner_details:
        analysis = analyze_corner_performance(session_df, corner)
        corner["score"] = analysis["score"]
        corner["grade"] = analysis["grade"]
        corner["metrics"] = analysis["metrics"]
        analyses.append(analysis)
    return analyses


@pytest.fixture(scope="module")
def score_data(session_df, corner_details, corner_analysis):
    return calculate_performance_score(session_df, corner_details)


class TestGeometryPipeline:
    def test_geometry_columns_added(self, session_df):
        for col in ("cumulative_distance", "curvature"):
            assert col in session_df.columns, f"calculate_trajectory_geometry must add {col}"

    def test_laps_detected(self, session_df):
        assert "lap_number" in session_df.columns
        assert session_df["lap_number"].nunique() >= 1

    def test_corners_detected(self, corner_details):
        assert len(corner_details) > 0
        for corner in corner_details:
            assert "id" in corner
            assert "apex_index" in corner


class TestCornerPerformance:
    def test_one_analysis_per_corner(self, corner_analysis, corner_details):
        assert len(corner_analysis) == len(corner_details)

    def test_analysis_payload_shape(self, corner_analysis):
        for analysis in corner_analysis:
            assert 0 <= analysis["score"] <= 100
            assert analysis["grade"] in {"A", "B", "C", "D", "F"}
            assert isinstance(analysis["metrics"], dict)
            assert "apex_speed_real" in analysis["metrics"]


class TestPerformanceScore:
    def test_overall_score_in_range(self, score_data):
        assert 0 <= score_data["overall_score"] <= 100

    def test_grade_and_percentile(self, score_data):
        assert score_data["grade"] in {"A", "B", "C", "D", "F"}
        assert 0 <= score_data["percentile"] <= 100

    def test_breakdown_present(self, score_data):
        breakdown = score_data["breakdown"]
        assert breakdown, "Score breakdown must not be empty"
        assert all(isinstance(v, (int, float)) for v in breakdown.values())


class TestCoaching:
    def test_advice_generated(self, session_df, corner_details, score_data, corner_analysis):
        advice = generate_coaching_advice(
            session_df, corner_details, score_data, corner_analysis, laps_analyzed=LAPS_ANALYZED
        )
        assert isinstance(advice, list)
        assert len(advice) > 0, "Pipeline must produce at least one coaching advice"
        for item in advice:
            assert isinstance(item, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
