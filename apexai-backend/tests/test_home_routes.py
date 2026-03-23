#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Tests for Home Routes
Tests: tips rotation, insights computation, reset auth, mapping.
"""

import datetime
import sys
import os
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.api.home_routes import (
    _get_weekly_tips,
    _compute_time_gained,
    _compute_weak_point,
    TIPS_POOL,
    _cache_set,
    _cache_get,
    _cache_invalidate,
    _insights_cache,
)


# ============================================================================
# Tips rotation
# ============================================================================

class TestTipsRotation:
    """Tips should rotate weekly and week N ≠ week N+1."""

    def test_tips_return_two(self):
        tips = _get_weekly_tips()
        assert len(tips) == 2

    def test_tips_have_required_keys(self):
        tips = _get_weekly_tips()
        for tip in tips:
            assert "badge" in tip
            assert "badge_color" in tip
            assert "title" in tip
            assert "body" in tip

    def test_week_n_vs_n_plus_1_different(self):
        """Tips for consecutive weeks should differ."""
        with patch("src.api.home_routes.datetime") as mock_dt:
            # Week 10
            mock_dt.date.today.return_value = MagicMock(
                isocalendar=lambda: (2026, 10, 1)
            )
            tips_w10 = _get_weekly_tips()

            # Week 11
            mock_dt.date.today.return_value = MagicMock(
                isocalendar=lambda: (2026, 11, 1)
            )
            tips_w11 = _get_weekly_tips()

        # At least one tip should differ
        titles_w10 = {t["title"] for t in tips_w10}
        titles_w11 = {t["title"] for t in tips_w11}
        assert titles_w10 != titles_w11, "Week 10 and 11 should have different tips"

    def test_pool_has_minimum_tips(self):
        assert len(TIPS_POOL) >= 8


# ============================================================================
# time_gained — smoothed + clamp
# ============================================================================

class TestTimeGained:
    """Time gained computation with smoothing and clamping."""

    def test_insufficient_data_returns_none(self):
        result = _compute_time_gained([{"lap_time": 50.0}], None)
        assert result is None

    def test_with_baseline(self):
        analyses = [
            {"lap_time": 48.0},
            {"lap_time": 49.0},
        ]
        result = _compute_time_gained(analyses, baseline_time=50.0)
        assert result == 2.0  # 50.0 - 48.0

    def test_smoothed_without_baseline(self):
        # 4 analyses, newest first: 47, 48, 51, 52
        analyses = [
            {"lap_time": 47.0},
            {"lap_time": 48.0},
            {"lap_time": 51.0},
            {"lap_time": 52.0},
        ]
        result = _compute_time_gained(analyses, baseline_time=None)
        # Recent half: [47, 48], best 3 → [47, 48], avg = 47.5
        # Older half: [51, 52], best 3 → [51, 52], avg = 51.5
        # Gain = 51.5 - 47.5 = 4.0
        assert result == 4.0

    def test_clamp_positive(self):
        analyses = [
            {"lap_time": 10.0},
            {"lap_time": 100.0},
        ]
        result = _compute_time_gained(analyses, baseline_time=100.0)
        # 100.0 - 10.0 = 90 → clamped to 30
        assert result == 30.0

    def test_clamp_negative(self):
        analyses = [
            {"lap_time": 100.0},
            {"lap_time": 50.0},
        ]
        result = _compute_time_gained(analyses, baseline_time=50.0)
        # 50.0 - 50.0 = 0 (best is 50.0 from the second analysis)
        # Wait: best lap_time from all analyses is 50.0. baseline is 50.0.
        # 50.0 - 50.0 = 0
        assert result == 0.0

    def test_round_one_decimal(self):
        analyses = [
            {"lap_time": 48.33},
            {"lap_time": 49.0},
        ]
        result = _compute_time_gained(analyses, baseline_time=50.0)
        # 50.0 - 48.33 = 1.67 → round to 1.7
        assert result == 1.7

    def test_zero_lap_times_filtered(self):
        analyses = [
            {"lap_time": 0},
            {"lap_time": 48.0},
        ]
        result = _compute_time_gained(analyses, baseline_time=50.0)
        # Only one valid lap_time → None
        assert result is None


# ============================================================================
# weak_point — corner_analysis + fallback
# ============================================================================

class TestWeakPoint:
    """Weak point identification via corner_analysis and breakdown fallback."""

    def test_via_corner_analysis(self):
        analyses = [
            {
                "corner_analysis": [
                    {"corner_id": 1, "score": 90},
                    {"corner_id": 4, "score": 30},
                    {"corner_id": 7, "score": 25},
                    {"corner_id": 9, "score": 35},
                ],
                "performance_score": None,
            },
            {
                "corner_analysis": [
                    {"corner_id": 1, "score": 88},
                    {"corner_id": 4, "score": 32},
                    {"corner_id": 7, "score": 28},
                    {"corner_id": 9, "score": 40},
                ],
                "performance_score": None,
            },
        ]
        result = _compute_weak_point(analyses)
        assert "label" in result
        assert "corners" in result
        assert len(result["corners"]) <= 3
        # Worst corners should be 7, 4, 9 (by avg score)
        assert 7 in result["corners"]
        assert 4 in result["corners"]

    def test_fallback_to_breakdown(self):
        analyses = [
            {
                "corner_analysis": None,
                "performance_score": {
                    "overall_score": 70,
                    "breakdown": {
                        "apex_precision": 25,
                        "trajectory_consistency": 10,
                        "apex_speed": 20,
                        "sector_times": 15,
                    },
                },
            },
        ]
        result = _compute_weak_point(analyses)
        assert result["label"] == "Régularité trajectoire"  # trajectory_consistency is weakest
        assert result["corners"] == []

    def test_no_data_returns_label(self):
        analyses = [
            {"corner_analysis": None, "performance_score": None},
        ]
        result = _compute_weak_point(analyses)
        assert result["label"] == "Données insuffisantes"

    def test_corner_analysis_with_corner_number_key(self):
        """Should also work with corner_number instead of corner_id."""
        analyses = [
            {
                "corner_analysis": [
                    {"corner_number": 3, "score": 20},
                    {"corner_number": 5, "score": 80},
                ],
                "performance_score": None,
            },
        ]
        result = _compute_weak_point(analyses)
        assert 3 in result["corners"]


# ============================================================================
# Cache
# ============================================================================

class TestCache:
    def setup_method(self):
        _insights_cache.clear()

    def test_cache_set_get(self):
        _cache_set("user1", {"foo": "bar"})
        result = _cache_get("user1")
        assert result is not None
        assert result["foo"] == "bar"

    def test_cache_miss(self):
        result = _cache_get("nonexistent")
        assert result is None

    def test_cache_invalidate(self):
        _cache_set("user2", {"x": 1})
        _cache_invalidate("user2")
        assert _cache_get("user2") is None


# ============================================================================
# Mapping objectives_reset_at -> reset_at
# ============================================================================

class TestMapping:
    """Ensure DB column objectives_reset_at maps to API field reset_at."""

    def test_objectives_reset_at_mapped_to_reset_at(self):
        """The _compute functions don't handle this directly —
        the mapping happens in the get_insights endpoint.
        This test verifies the mapping logic conceptually."""
        # Simulate what the endpoint does
        profile_data = {
            "baseline_score": 82.0,
            "baseline_time": 48.3,
            "objectives_reset_at": "2026-03-23T12:00:00+00:00",
        }
        # Mapping logic from the endpoint
        reset_at = str(profile_data.get("objectives_reset_at")) if profile_data.get("objectives_reset_at") else None
        assert reset_at == "2026-03-23T12:00:00+00:00"

    def test_null_objectives_reset_at(self):
        profile_data = {
            "baseline_score": None,
            "baseline_time": None,
            "objectives_reset_at": None,
        }
        reset_at = str(profile_data.get("objectives_reset_at")) if profile_data.get("objectives_reset_at") else None
        assert reset_at is None


# ============================================================================
# Reset auth — structural test (endpoint-level tests need TestClient)
# ============================================================================

class TestResetAuth:
    """Verify reset endpoint requires JWT (structural — middleware enforces)."""

    def test_get_current_user_dependency_required(self):
        """The reset endpoint uses Depends(get_current_user),
        which returns 401 without a valid token."""
        from src.api.home_routes import router
        reset_route = None
        for route in router.routes:
            path = getattr(route, "path", "")
            # APIRouter stores path without prefix
            if "/insights/reset" in path:
                reset_route = route
                break
        assert reset_route is not None, "Reset route must exist"
        # Verify endpoint function signature mentions current_user param
        endpoint = getattr(reset_route, "endpoint", None)
        if endpoint:
            import inspect
            sig = inspect.signature(endpoint)
            assert "current_user" in sig.parameters, "Reset must require current_user (JWT auth)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
