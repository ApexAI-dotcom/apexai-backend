"""La note suit les mesures : plus il reste de temps à gagner, plus elle baisse."""
from src.analysis.scoring import rescore_from_measures

BASE = {"overall_score": 80.0, "grade": "A",
        "breakdown": {"apex_precision": 22.0, "trajectory_consistency": 20.0, "apex_speed": 20.0, "sector_times": 15.0},
        "details": {}}
CORNERS = [{"speed_efficiency": 0.95}, {"speed_efficiency": 0.9}]


def test_more_time_to_gain_means_lower_score():
    laps = [61.2, 61.4, 61.5, 61.6]
    a = rescore_from_measures(BASE, laps, 1.6, CORNERS)
    b = rescore_from_measures(BASE, laps, 0.4, CORNERS)
    assert a["overall_score"] < b["overall_score"]
    assert a["overall_score"] == sum(a["breakdown"].values())
    assert a["details"]["potential_gain_pct"] > 2


def test_irregular_laps_lower_the_consistency():
    steady = rescore_from_measures(BASE, [60.0, 60.1, 60.2], 0.5, CORNERS)
    messy = rescore_from_measures(BASE, [60.0, 62.0, 63.0], 0.5, CORNERS)
    assert messy["breakdown"]["trajectory_consistency"] < steady["breakdown"]["trajectory_consistency"]


def test_single_lap_keeps_unmeasurable_criteria():
    one = rescore_from_measures(BASE, [68.63], None, CORNERS)
    assert one["breakdown"]["apex_speed"] == 20.0
    assert one["breakdown"]["trajectory_consistency"] == 20.0
