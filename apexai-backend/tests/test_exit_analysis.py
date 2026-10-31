import numpy as np
import pandas as pd

from src.analysis.exit_analysis import analyze_corner_exits, exit_advice


def _session(n_laps=8):
    """Un virage à 300 m : plus le point le plus lent est tardif, meilleure est la sortie."""
    rows, per_lap = [], []
    t0, d0 = 0.0, 0.0
    rng = np.random.default_rng(1)
    for lap in range(1, n_laps + 1):
        shift = float(rng.uniform(-6, 6))          # position du point le plus lent / corde
        exit_bonus = 0.5 * shift                   # tourner plus tard -> meilleure sortie
        d = np.arange(0, 600, 2.0)
        v = 100 - 45 * np.exp(-((d - 300 - shift) ** 2) / 900)
        after = d > 300 + shift
        v = v + np.where(after, exit_bonus * (1 - np.exp(-(d - 300 - shift) / 40)), 0)
        t = np.concatenate([[0], np.cumsum(np.diff(d) / (v[1:] / 3.6))])
        start = len(rows)
        for k in range(len(d)):
            rows.append({"lap_number": lap, "cumulative_distance": d0 + d[k], "speed": v[k], "time": t0 + t[k],
                         "lateral_g": 1.5 if abs(d[k] - 300) < 20 else 0.2, "rpm": 9000 + 40 * v[k]})
        apex = start + int(np.argmin(np.abs(d - 300)))
        per_lap.append({"lap": lap, "entry_index": apex - 30, "apex_index": apex, "exit_index": apex + 20})
        t0 += t[-1]
        d0 += d[-1]
    return pd.DataFrame(rows), {"corner_id": 3, "per_lap_data": per_lap}


def test_later_apex_on_best_exits_is_detected_and_explained():
    df, corner = _session()
    stats = analyze_corner_exits(df, corner, None)
    assert stats is not None and stats["laps"] == 8
    assert stats["levers"]["apex_shift_m"]["diff"] > 3
    assert stats["relance_gain_s"] > 0
    adv = exit_advice("Virage 3 à droite", stats, {"corner": 0.0, "relance": 0.0})
    assert adv is not None and adv["category"] == "exit"
    assert "plus loin" in adv["explanation"]
    assert "enroule" in adv["explanation"]


def test_no_advice_without_enough_laps():
    df, corner = _session(n_laps=3)
    assert analyze_corner_exits(df, corner, None) is None
