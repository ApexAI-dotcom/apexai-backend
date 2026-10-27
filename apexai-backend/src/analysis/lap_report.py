#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Rapports « à la Race Studio » sur les tours d'une séance.

Quatre vues calculées sur les canaux réellement présents dans le fichier :

- laps      : tableau par tour (temps, vitesse max/min, régime max/min,
              température d'eau max, g latéral max, freinage max, batterie
              du kart mini) — l'équivalent du « Channels report » ;
- sectors   : temps de chaque tour en 3 secteurs de même longueur, meilleur
              secteur, tour théorique (somme des meilleurs secteurs) et
              meilleur tour glissant (le tour le plus rapide sur n'importe
              quelle portion d'un tour de long) — le « Split report » ;
- gg        : nuage accélération latérale × longitudinale du meilleur tour,
              coloré par la vitesse — le diagramme G-G ;
- rpm_hist  : temps passé par plage de régime sur les tours complets.

Un canal absent du fichier donne une colonne vide, jamais une valeur inventée.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

G = 9.81


def _col(df: pd.DataFrame, names: Sequence[str]) -> Optional[str]:
    cols = {c.lower(): c for c in df.columns}
    for n in names:
        if n in cols:
            return cols[n]
    return None


def _num(df: pd.DataFrame, col: Optional[str]) -> Optional[np.ndarray]:
    if not col:
        return None
    s = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
    return s if np.isfinite(s).sum() >= 5 else None


def _r(x: Optional[float], nd: int = 2) -> Optional[float]:
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def _channels(df: pd.DataFrame) -> Dict[str, Optional[np.ndarray]]:
    speed = _num(df, _col(df, ["speed_kmh", "speed"]))
    if speed is not None and np.nanmax(speed) < 60:  # m/s -> km/h
        speed = speed * 3.6
    lat = _num(df, _col(df, ["gps latacc", "lateral_g"]))
    lon = _num(df, _col(df, ["gps lonacc", "longitudinal_g", "lon_g"]))
    ext = _num(df, _col(df, ["external voltage", "battery voltage", "batt"]))
    # Une tension externe quasi nulle = pas de batterie branchée sur le boîtier
    if ext is not None and np.nanmedian(ext) < 5:
        ext = None
    return {
        "time": _num(df, _col(df, ["time"])),
        "dist": _num(df, _col(df, ["cumulative_distance"])),
        "lap": _num(df, _col(df, ["lap_number"])),
        "speed": speed,
        "rpm": _num(df, _col(df, ["rpm", "engine rpm", "engine_rpm"])),
        "water": _num(df, _col(df, ["water temp", "water_temp", "watertemp", "h2o temp"])),
        "exhaust": _num(df, _col(df, ["exhaust temp", "egt", "exhaust_temp"])),
        "lat": lat,
        "lon": lon,
        "battery": ext,
    }


def _nanmax(a: Optional[np.ndarray], m: np.ndarray) -> Optional[float]:
    if a is None:
        return None
    v = a[m]
    v = v[np.isfinite(v)]
    return float(v.max()) if len(v) else None


def _nanmin(a: Optional[np.ndarray], m: np.ndarray) -> Optional[float]:
    if a is None:
        return None
    v = a[m]
    v = v[np.isfinite(v)]
    return float(v.min()) if len(v) else None


def _lon_from_speed(ch: Dict[str, Optional[np.ndarray]]) -> Optional[np.ndarray]:
    """Accélération longitudinale déduite de la vitesse GPS quand le boîtier ne la donne pas."""
    v, t = ch["speed"], ch["time"]
    if v is None or t is None:
        return None
    with np.errstate(divide="ignore", invalid="ignore"):
        a = np.gradient(v / 3.6, t) / G
    # lissage léger (5 points) : la dérivée de la vitesse GPS est bruitée
    k = np.ones(5) / 5
    return np.convolve(np.nan_to_num(a), k, mode="same")


def build_lap_report(
    df: pd.DataFrame,
    lap_times: Dict[int, float],
    lap_bounds: Optional[Dict[int, Tuple[float, float]]] = None,
    n_sectors: int = 3,
) -> Dict[str, Any]:
    """Rapports par tour. lap_times : tours complets retenus {numéro: temps exact}."""
    if df is None or df.empty or not lap_times:
        return {"available": False}
    ch = _channels(df)
    t, dist, lapn = ch["time"], ch["dist"], ch["lap"]
    if t is None or lapn is None:
        return {"available": False}
    lon_derived = False
    if ch["lon"] is None:
        ch["lon"] = _lon_from_speed(ch)
        lon_derived = ch["lon"] is not None

    laps = sorted(int(k) for k in lap_times)
    best = min(laps, key=lambda k: lap_times[k])

    # ------------------------------------------------------------ tableau par tour
    rows: List[Dict[str, Any]] = []
    for k in laps:
        m = lapn == k
        if not m.any():
            continue
        lat = ch["lat"]
        lon = ch["lon"]
        rows.append({
            "lap": k,
            "time_s": round(float(lap_times[k]), 3),
            "gap_s": round(float(lap_times[k] - lap_times[best]), 3),
            "is_best": k == best,
            "speed_max": _r(_nanmax(ch["speed"], m), 1),
            "speed_min": _r(_nanmin(ch["speed"], m), 1),
            "rpm_max": _r(_nanmax(ch["rpm"], m), 0),
            "rpm_min": _r(_nanmin(ch["rpm"], m), 0),
            "water_max": _r(_nanmax(ch["water"], m), 1),
            "exhaust_max": _r(_nanmax(ch["exhaust"], m), 0),
            "lat_g_max": _r(_nanmax(np.abs(lat) if lat is not None else None, m), 2),
            "brake_g_max": _r(-(_nanmin(lon, m) or 0.0) if lon is not None else None, 2),
            "battery_min": _r(_nanmin(ch["battery"], m), 2),
        })
    available = {
        key: any(r.get(key) is not None for r in rows)
        for key in ("speed_max", "rpm_max", "water_max", "exhaust_max", "lat_g_max", "brake_g_max", "battery_min")
    }

    # ------------------------------------------------------------ secteurs
    sectors: Optional[Dict[str, Any]] = None
    if dist is not None:
        per_lap = []
        lengths = []
        for k in laps:
            m = (lapn == k) & np.isfinite(dist) & np.isfinite(t)
            if m.sum() < 10:
                continue
            d = dist[m] - dist[m][0]
            lengths.append(float(d[-1]))
            per_lap.append((k, d, t[m]))
        if len(per_lap) >= 2:
            L = float(np.median(lengths))
            bounds = [L * i / n_sectors for i in range(1, n_sectors)]
            table = []
            for k, d, tt in per_lap:
                t0, t1 = (lap_bounds or {}).get(k, (float(tt[0]), float(tt[0]) + lap_times[k]))
                # Coupures à la même fraction de chaque tour (la distance GPS varie de quelques mètres)
                cuts = [float(np.interp(d[-1] * i / n_sectors, d, tt)) for i in range(1, n_sectors)]
                edges = [t0] + cuts + [t1]
                secs = [round(edges[i + 1] - edges[i], 3) for i in range(n_sectors)]
                if any(s <= 0 for s in secs):
                    continue
                table.append({"lap": k, "times": secs, "total_s": round(float(lap_times[k]), 3)})
            if len(table) >= 2:
                best_secs = [min(r["times"][i] for r in table) for i in range(n_sectors)]
                theoretical = round(sum(best_secs), 3)
                # Meilleur tour glissant : le tour le plus rapide en partant de n'importe
                # quel point, sur des tours consécutifs. La position est exprimée en
                # fraction de tour (tour k, 0 à 1) pour qu'une fenêtre fasse exactement un
                # tour même si la distance GPS varie de quelques mètres d'un tour à l'autre.
                rolling = None
                kept = {r["lap"] for r in table}
                prof = {k: (d, tt) for k, d, tt in per_lap if k in kept}
                ks = sorted(prof)
                runs, cur = [], [ks[0]]
                for a, b in zip(ks, ks[1:]):
                    if b == a + 1:
                        cur.append(b)
                    else:
                        runs.append(cur)
                        cur = [b]
                runs.append(cur)
                for run in runs:
                    if len(run) < 2:
                        continue
                    P, T = [], []
                    for i, k in enumerate(run):
                        d, tt = prof[k]
                        t0, t1 = (lap_bounds or {}).get(k, (float(tt[0]), float(tt[0]) + lap_times[k]))
                        frac = np.clip(d / max(d[-1], 1.0), 0, 1)
                        P.extend([i] + list(i + frac) + [i + 1])
                        T.extend([t0] + list(tt) + [t1])
                    P, T = np.asarray(P), np.asarray(T)
                    order = np.lexsort((T, P))
                    P, T = P[order], T[order]
                    starts = P <= P[-1] - 1.0
                    if starts.any():
                        t_end = np.interp(P[starts] + 1.0, P, T)
                        cand = float(np.min(t_end - T[starts]))
                        rolling = cand if rolling is None else min(rolling, cand)
                best_time = float(lap_times[best])
                if rolling is not None:
                    rolling = round(min(rolling, best_time), 3)
                sectors = {
                    "n": n_sectors,
                    "length_m": round(L, 1),
                    "bounds_m": [round(b, 1) for b in bounds],
                    "laps": table,
                    "best": best_secs,
                    "theoretical_s": theoretical,
                    "rolling_best_s": rolling,
                    "best_lap_s": round(best_time, 3),
                }

    # ------------------------------------------------------------ diagramme G-G (meilleur tour)
    gg = None
    if ch["lat"] is not None and ch["lon"] is not None:
        m = (lapn == best) & np.isfinite(ch["lat"]) & np.isfinite(ch["lon"])
        if m.sum() >= 20:
            idx = np.flatnonzero(m)
            step = max(1, len(idx) // 500)
            idx = idx[::step]
            sp = ch["speed"]
            gg = {
                "lap": best,
                "lat": [round(float(x), 2) for x in ch["lat"][idx]],
                "lon": [round(float(x), 2) for x in ch["lon"][idx]],
                "speed": [round(float(x), 1) for x in sp[idx]] if sp is not None else None,
                "lon_source": "vitesse GPS" if lon_derived else "boîtier",
                "lat_max": _r(float(np.nanmax(np.abs(ch["lat"][m]))), 2),
                "brake_max": _r(float(-np.nanmin(ch["lon"][m])), 2),
                "accel_max": _r(float(np.nanmax(ch["lon"][m])), 2),
            }

    # ------------------------------------------------------------ histogramme du régime
    rpm_hist = None
    rpm = ch["rpm"]
    if rpm is not None:
        m = np.isin(lapn, laps) & np.isfinite(rpm) & (rpm > 1000)
        if m.sum() >= 20:
            dt = np.diff(t, append=t[-1])
            dt = np.clip(np.nan_to_num(dt), 0, 1.0)
            r, w = rpm[m], dt[m]
            step = 500
            lo = int(np.floor(np.percentile(r, 0.5) / step) * step)
            hi = int(np.ceil(np.percentile(r, 99.5) / step) * step)
            edges = np.arange(lo, hi + step, step)
            if len(edges) >= 2:
                hist, _ = np.histogram(np.clip(r, lo, hi - 1e-6), bins=edges, weights=w)
                total = float(hist.sum()) or 1.0
                rpm_hist = {
                    "step": step,
                    "bins": [
                        {"from": int(edges[i]), "to": int(edges[i + 1]), "seconds": round(float(hist[i]), 1), "share": round(float(hist[i]) / total, 4)}
                        for i in range(len(hist))
                    ],
                    "laps": laps,
                    "p50": int(np.percentile(r, 50)),
                    "p95": int(np.percentile(r, 95)),
                }

    return {
        "available": bool(rows),
        "best_lap": best,
        "laps": rows,
        "columns": available,
        "sectors": sectors,
        "gg": gg,
        "rpm_hist": rpm_hist,
    }
