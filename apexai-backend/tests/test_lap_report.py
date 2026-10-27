"""Rapports par tour (tableau, secteurs, G-G, régime) sur une séance synthétique."""

import numpy as np
import pandas as pd

from src.analysis.lap_report import build_lap_report


def _session(n_laps=4, lap_len=1000.0, hz=10):
    rows, t, d = [], 0.0, 0.0
    times = {}
    for k in range(1, n_laps + 1):
        v = 20.0 + k * 0.2  # m/s, un peu plus vite à chaque tour
        lap_t = lap_len / v
        times[k] = lap_t
        n = int(lap_t * hz)
        for i in range(n):
            frac = i / n
            rows.append({
                "time": t + frac * lap_t, "cumulative_distance": d + frac * lap_len, "lap_number": k,
                "speed": v * 3.6 * (0.8 + 0.4 * abs(np.sin(frac * np.pi * 4))),
                "rpm": str(9000 + 3000 * abs(np.sin(frac * np.pi * 4))), "water temp": str(50 + k),
                "gps latacc": str(2.0 * np.sin(frac * np.pi * 8)), "gps lonacc": str(np.cos(frac * np.pi * 8)),
            })
        t += lap_t
        d += lap_len
    return pd.DataFrame(rows), times


def test_report_tables():
    df, times = _session()
    bounds, t0 = {}, 0.0
    for k in sorted(times):
        bounds[k] = (t0, t0 + times[k])
        t0 += times[k]
    r = build_lap_report(df, times, bounds)
    assert r["available"] and r["best_lap"] == 4
    assert [l["lap"] for l in r["laps"]] == [1, 2, 3, 4]
    assert r["laps"][-1]["water_max"] == 54.0
    assert r["columns"]["rpm_max"] and not r["columns"]["battery_min"]
    s = r["sectors"]
    for lap in s["laps"]:
        assert abs(sum(lap["times"]) - lap["total_s"]) < 0.01
    assert s["theoretical_s"] <= s["best_lap_s"] + 1e-6
    assert s["rolling_best_s"] <= s["best_lap_s"] + 1e-6
    assert r["gg"]["lap"] == 4 and len(r["gg"]["lat"]) == len(r["gg"]["lon"])
    assert abs(sum(b["share"] for b in r["rpm_hist"]["bins"]) - 1) < 0.01


def test_missing_channels_stay_empty():
    df, times = _session()
    df = df.drop(columns=["rpm", "water temp", "gps latacc", "gps lonacc"])
    r = build_lap_report(df, times)
    assert r["rpm_hist"] is None
    assert all(l["rpm_max"] is None and l["water_max"] is None for l in r["laps"])
    assert r["gg"] is None  # sans accélération latérale, pas de diagramme
