# -*- coding: utf-8 -*-
"""
Faits mesurés : ce que la télémétrie dit de chaque virage et de la séance.

Cette couche ne conseille rien. Elle transforme les sorties des modules
d'analyse (virages, freinages, sorties, tour idéal) et le fichier lui-même
(régime, eau, appui latéral) en faits chiffrés, tous optionnels : un canal
absent laisse simplement le fait à None, et les principes qui en ont besoin
se taisent. Rien ne bloque jamais l'analyse.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

G = 9.81


def _num(df: pd.DataFrame, col: str) -> Optional[np.ndarray]:
    if col not in df.columns:
        return None
    x = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(x).any():
        return None
    return x


def _f(v, default=None) -> Optional[float]:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _smooth(x: np.ndarray, n: int = 5) -> np.ndarray:
    return pd.Series(x).rolling(n, center=True, min_periods=1).mean().to_numpy()


# ─────────────────────────────────────────────────────────────────────────────
# Virage
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CornerFacts:
    id: int
    direction: str                     # « à droite » / « à gauche » / ""
    kind: str                          # epingle | lent | moyen | rapide
    kind_source: str                   # circuit | mesure
    angle_deg: Optional[float]
    radius_m: Optional[float]
    pos_m: float                       # position dans le tour (corde)
    to_next_m: Optional[float]         # distance jusqu'au virage suivant
    straight_after_m: Optional[float]  # ligne droite qui suit (≈ to_next - zones de virage)
    opens_longest_straight: bool
    time_lost: float                   # perte mesurée sur le virage (tour idéal)
    best_lap_here: Optional[int]
    recurring: bool
    lap_spread_s: Optional[float]
    apex_speed: Optional[float]
    apex_speed_best: Optional[float]
    apex_error_m: float
    apex_error_dir: Optional[str]
    entry_speed: Optional[float]
    lateral_g: Optional[float]
    raw: Dict[str, Any]                # dictionnaire de virage d'origine (freinage, etc.)
    exits: Optional[Dict[str, Any]] = None     # synthèse exit_analysis
    phase: Optional[Dict[str, Any]] = None     # temps mort / appui, mesuré ici
    rpm_min: Optional[float] = None            # régime médian au point le plus lent
    rpm_min_best: Optional[float] = None       # sur les meilleures sorties

    @property
    def head(self) -> str:
        return f"Virage {self.id} {self.direction}".strip()

    @property
    def kind_fr(self) -> str:
        return {"epingle": "épingle", "lent": "virage lent", "moyen": "virage moyen",
                "rapide": "virage rapide"}.get(self.kind, "virage")


# ─────────────────────────────────────────────────────────────────────────────
# Séance
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EngineCurve:
    """Accélération mesurée sur les relances, par plage de régime."""
    bins: List[Dict[str, float]]
    peak_rpm: float
    peak_g: float
    knee_rpm: float           # régime à partir duquel le moteur pousse vraiment (≥ 85 % du pic)
    top_rpm: float            # régime de bout de ligne droite (médiane des maxima par tour)
    top_plateau_s: float      # temps par tour collé en haut du compte-tours sans accélérer


@dataclass
class SessionFacts:
    laps_used: List[int]
    lap_times: Dict[int, float]
    best_lap: Optional[int]
    best_lap_time: Optional[float]
    median_lap_time: Optional[float]
    ideal_gain_s: Optional[float]
    vmax: Optional[float]
    has_rpm: bool
    has_water: bool
    engine: Optional[EngineCurve] = None
    water_by_lap: Dict[int, float] = field(default_factory=dict)
    grip_by_lap: Dict[int, float] = field(default_factory=dict)     # appui latéral p95 par tour
    grip_warmup_laps: Optional[int] = None                           # tours pour atteindre 97 % du plateau
    grip_fade_pct: Optional[float] = None                            # chute en fin de séance
    longest_straight_m: Optional[float] = None
    first_lap_number: Optional[int] = None


def _lap_frames(df: pd.DataFrame, laps: List[int]) -> Dict[int, pd.DataFrame]:
    out = {}
    for lap, g in df[df["lap_number"].isin(laps)].groupby("lap_number"):
        if len(g) >= 30:
            out[int(lap)] = g
    return out


def _engine_curve(frames: Dict[int, pd.DataFrame]) -> Optional[EngineCurve]:
    rs, axs, lats, tops, plateaus = [], [], [], [], []
    for lap, g in frames.items():
        r = _num(g, "rpm")
        v = _num(g, "speed")
        t = _num(g, "time")
        lat = _num(g, "lateral_g")
        if r is None or v is None or t is None or np.nanmax(r) < 3000:
            return None
        dt = np.diff(t)
        if not len(dt) or np.nanmedian(dt) <= 0:
            continue
        ax = _smooth(np.gradient(v / 3.6, t) / G, 5)
        la = np.abs(lat) if lat is not None else np.zeros_like(r)
        rs.append(r); axs.append(ax); lats.append(la)
        tops.append(float(np.nanpercentile(r, 99.5)))
    if not rs:
        return None
    r = np.concatenate(rs); ax = np.concatenate(axs); la = np.concatenate(lats)
    top = float(np.median(tops))
    # Collé en haut du compte-tours sans accélérer : rupteur ou démultiplication trop courte.
    for g in frames.values():
        rr = _num(g, "rpm"); v = _num(g, "speed"); t = _num(g, "time")
        a = _smooth(np.gradient(v / 3.6, t) / G, 5)
        dt = np.r_[np.diff(t), 0.0]
        m = (rr >= top - 220) & (a < 0.02) & (a > -0.15)
        plateaus.append(float(dt[m].sum()))
    drive = (ax > 0.03) & (la < 0.7) & np.isfinite(r)
    bins = []
    for b in range(5000, 17000, 500):
        s = drive & (r >= b) & (r < b + 500)
        if s.sum() >= 25:
            bins.append({"rpm": b + 250, "g": float(np.median(ax[s])), "n": int(s.sum())})
    if len(bins) < 4:
        return None
    peak = max(bins, key=lambda x: x["g"])
    knee = peak["rpm"]
    for bb in bins:
        if bb["rpm"] <= peak["rpm"] and bb["g"] >= 0.85 * peak["g"]:
            knee = bb["rpm"]
            break
    return EngineCurve(bins=bins, peak_rpm=peak["rpm"], peak_g=peak["g"], knee_rpm=float(knee),
                       top_rpm=top, top_plateau_s=float(np.median(plateaus)) if plateaus else 0.0)


def _grip_curve(frames: Dict[int, pd.DataFrame]) -> Dict[int, float]:
    out = {}
    for lap, g in frames.items():
        lat = _num(g, "lateral_g")
        if lat is not None:
            out[lap] = float(np.nanpercentile(np.abs(lat), 95))
    return out


def session_facts(df: pd.DataFrame, laps_used: List[int], ideal_lap: Optional[Dict[str, Any]],
                  lap_times: Optional[Dict[int, float]] = None) -> SessionFacts:
    laps_used = sorted(int(x) for x in (laps_used or []))
    if not laps_used and "lap_number" in df.columns:
        laps_used = sorted(int(x) for x in df["lap_number"].unique() if x and x > 0)
    frames = _lap_frames(df, laps_used)
    if lap_times is None:
        lap_times = {}
        for lap, g in frames.items():
            t = _num(g, "time")
            if t is not None:
                lap_times[lap] = float(np.nanmax(t) - np.nanmin(t))
    lt = {k: v for k, v in lap_times.items() if k in frames} or lap_times
    best_lap = min(lt, key=lt.get) if lt else None
    sf = SessionFacts(
        laps_used=laps_used, lap_times=lt, best_lap=best_lap,
        best_lap_time=lt.get(best_lap) if best_lap else None,
        median_lap_time=float(np.median(list(lt.values()))) if lt else None,
        ideal_gain_s=_f((ideal_lap or {}).get("potential_gain_s")),
        vmax=_f(np.nanmax(_num(df, "speed"))) if _num(df, "speed") is not None else None,
        has_rpm=_num(df, "rpm") is not None and float(np.nanmax(_num(df, "rpm"))) > 3000,
        has_water=_num(df, "water temp") is not None,
        first_lap_number=laps_used[0] if laps_used else None,
    )
    try:
        sf.engine = _engine_curve(frames) if sf.has_rpm else None
    except Exception:
        sf.engine = None
    if sf.has_water:
        for lap, g in frames.items():
            w = _num(g, "water temp")
            if w is not None and np.isfinite(w).any():
                sf.water_by_lap[lap] = float(np.nanmax(w))
    sf.grip_by_lap = _grip_curve(frames)
    gl = [sf.grip_by_lap[k] for k in sorted(sf.grip_by_lap)]
    if len(gl) >= 6:
        plateau = float(np.median(sorted(gl)[-max(3, len(gl) // 2):]))
        sf.grip_warmup_laps = next((i for i, x in enumerate(gl) if x >= 0.97 * plateau), None)
        end = float(np.mean(gl[-3:]))
        peak = float(np.max(gl[:-2])) if len(gl) > 3 else plateau
        sf.grip_fade_pct = round(max(0.0, (peak - end) / peak * 100.0), 1) if peak > 0 else None
    return sf


# ─────────────────────────────────────────────────────────────────────────────
# Classement des virages : base circuits d'abord, mesure ensuite
# ─────────────────────────────────────────────────────────────────────────────

def _catalog_corners(circuit: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Virages de la fiche circuit, avec la position GPS de leur corde."""
    if not circuit or not circuit.get("slug"):
        return []
    try:
        from src.core import circuit_catalog as cc
        full = cc.get(circuit["slug"]) or {}
    except Exception:
        return []
    line = full.get("centerline") or []
    corners = full.get("corners") or []
    if len(line) < 10 or not corners:
        return []
    pts = np.asarray([(float(p[0]), float(p[1])) for p in line])
    lat0 = math.radians(float(np.mean(pts[:, 0])))
    xy = np.c_[pts[:, 1] * 111320 * math.cos(lat0), pts[:, 0] * 110540]
    d = np.r_[0.0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]
    out = []
    for c in corners:
        a = _f(c.get("apex_m"))
        if a is None:
            continue
        out.append({**c, "apex_lat": float(np.interp(a, d, pts[:, 0])),
                    "apex_lon": float(np.interp(a, d, pts[:, 1]))})
    return out


def _dist_m(lat1, lon1, lat2, lon2) -> float:
    k = math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lon2 - lon1) * 111320 * k, (lat2 - lat1) * 110540)


def _measured_kind(apex_speed: Optional[float], vmax: Optional[float], angle: Optional[float]) -> str:
    """Sans fiche circuit : la vitesse au point le plus lent, rapportée à la vitesse de pointe, classe le virage."""
    if apex_speed is None or not vmax:
        return "moyen"
    r = apex_speed / vmax
    if r < 0.42 or (angle is not None and angle >= 160 and r < 0.50):
        return "epingle"
    if r < 0.55:
        return "lent"
    if r >= 0.75:
        return "rapide"
    return "moyen"


def _heading_change(df: pd.DataFrame, i0: int, i1: int) -> Optional[float]:
    h = _num(df, "heading")
    if h is None or i0 < 0 or i1 >= len(df) or i1 <= i0:
        return None
    seg = np.unwrap(np.radians(h[i0:i1 + 1]))
    return float(abs(math.degrees(seg[-1] - seg[0])))


def _phase(df: pd.DataFrame, c: Dict[str, Any], laps: List[int]) -> Optional[Dict[str, Any]]:
    """
    Ce qui se passe entre la fin du freinage et la remise des gaz.

    Sans capteur de gaz, un temps « sans frein ni gaz » mesuré sur la seule
    vitesse confond deux situations opposées :
      - roue libre : gaz coupés, le kart décélère (≈ −0,1 g) sans appui fort ;
      - kart en appui qui ne repart pas : gaz ouverts, mais le châssis frotte et
        retient le moteur ; la vitesse stagne alors sous un fort appui latéral.
    La décélération moyenne et l'appui mesurés pendant cette phase les séparent.
    """
    rows = []
    t_all = _num(df, "time"); v_all = _num(df, "speed"); d_all = _num(df, "cumulative_distance")
    lat_all = _num(df, "lateral_g")
    if t_all is None or v_all is None or d_all is None:
        return None
    for p in c.get("per_lap_data") or []:
        if laps and p.get("lap") not in laps:
            continue
        i = int(p.get("apex_index", -1))
        if i < 0 or i >= len(df):
            continue
        lap = df["lap_number"].iloc[i]
        idx = np.flatnonzero(df["lap_number"].to_numpy() == lap)
        if len(idx) < 30:
            continue
        d = d_all[idx]; v = v_all[idx]; t = t_all[idx]
        la = np.abs(lat_all[idx]) if lat_all is not None else None
        ax = _smooth(np.gradient(v / 3.6, t) / G, 5)
        ad = d_all[i]
        win = (d >= ad - 30) & (d <= ad + 30)
        if win.sum() < 3:
            continue
        w = np.flatnonzero(win)
        m = w[np.argmin(v[w])]
        # fin du vrai freinage avant le point le plus lent
        k = m
        while k > 0 and d[m] - d[k] < 80 and ax[k] > -0.22:
            k -= 1
        b_end = k + 1
        thr = m
        while thr < len(ax) - 1 and d[thr] - d[m] < 60 and ax[thr] < 0.06:
            thr += 1
        if b_end >= thr:
            continue
        seg = slice(b_end, thr + 1)
        dur = float(t[thr] - t[b_end])
        rows.append({
            "lap": int(p.get("lap")), "neutral_s": dur,
            "neutral_ax": float(np.mean(ax[seg])),
            "neutral_lat": float(np.mean(la[seg])) if la is not None else None,
            "peak_lat": float(np.nanmax(la[max(0, m - 15):m + 15])) if la is not None else None,
        })
    if len(rows) < 4:
        return None
    med = lambda k: float(np.median([r[k] for r in rows if r.get(k) is not None])) if any(r.get(k) is not None for r in rows) else None  # noqa: E731
    best = min(rows, key=lambda r: r["neutral_s"])
    return {"neutral_s": med("neutral_s"), "neutral_ax": med("neutral_ax"),
            "neutral_lat": med("neutral_lat"), "peak_lat": med("peak_lat"),
            "best_s": best["neutral_s"], "best_lap": best["lap"], "laps": len(rows)}


def corner_facts(df: pd.DataFrame, corner_analysis: List[Dict[str, Any]], laps_used: List[int],
                 ideal_lap: Optional[Dict[str, Any]], session: SessionFacts,
                 circuit: Optional[Dict[str, Any]] = None) -> List[CornerFacts]:
    from src.analysis.exit_analysis import analyze_corner_exits
    from src.analysis.coaching import _corner_track_order

    cat = _catalog_corners(circuit)
    order = _corner_track_order(df, corner_analysis)
    gaps = [r.get("to_next_m") or 0 for r in order]
    longest_i = int(np.argmax(gaps)) if gaps else -1
    out: List[CornerFacts] = []
    for k, r in enumerate(order):
        c = r["corner"]
        cid = c.get("corner_id")
        if cid is None:
            continue
        ctype = (c.get("corner_type") or "").lower()
        direction = "à droite" if ctype == "right" else "à gauche" if ctype == "left" else ""
        apex_speed = _f(c.get("apex_speed_real"))
        to_next = r.get("to_next_m")
        offset = (to_next - 40.0) if to_next else None
        try:
            ex = analyze_corner_exits(df, c, laps_used, offset)
        except Exception:
            ex = None
        # Fiche circuit : virage dont la corde est à moins de 25 m.
        kind, src, angle, radius = None, "mesure", None, None
        alat, alon = _f(c.get("apex_lat")), _f(c.get("apex_lon"))
        if cat and alat is not None and alon is not None:
            best = min(cat, key=lambda x: _dist_m(alat, alon, x["apex_lat"], x["apex_lon"]))
            if _dist_m(alat, alon, best["apex_lat"], best["apex_lon"]) <= 25:
                kind = {"epingle": "epingle", "moyen": "moyen", "rapide": "rapide",
                        "lent": "lent"}.get(best.get("kind"), None)
                angle, radius, src = _f(best.get("angle_deg")), _f(best.get("min_radius_m")), "circuit"
        if angle is None:
            angle = _heading_change(df, int(c.get("entry_index", -1)), int(c.get("apex_index", -1)) + 25) \
                if c.get("entry_index") is not None else None
        if kind is None:
            mins = [p.get("min_speed") for p in (ex or {}).get("per_lap") or [] if p.get("min_speed")]
            kind = _measured_kind(float(np.median(mins)) if mins else apex_speed, session.vmax, angle)
            src = "mesure"
        elif kind == "moyen" and apex_speed is not None and session.vmax and apex_speed >= 0.78 * session.vmax:
            kind = "rapide"
        rpm_min = rpm_best = None
        if ex:
            rpms = [p.get("rpm_min") for p in ex.get("per_lap") or [] if p.get("rpm_min")]
            if rpms:
                rpm_min = float(np.median(rpms))
                third = max(2, len(ex["per_lap"]) // 3)
                rb = [p.get("rpm_min") for p in ex["per_lap"][:third] if p.get("rpm_min")]
                rpm_best = float(np.mean(rb)) if rb else None
        try:
            ph = _phase(df, c, laps_used)
        except Exception:
            ph = None
        best_apex = None
        speeds = [_f(p.get("apex_speed_kmh")) for p in c.get("per_lap_data") or []
                  if not laps_used or p.get("lap") in laps_used]
        speeds = [s for s in speeds if s]
        if speeds:
            best_apex = float(np.percentile(speeds, 85))
        out.append(CornerFacts(
            id=int(cid), direction=direction, kind=kind, kind_source=src, angle_deg=angle,
            radius_m=radius, pos_m=float(r.get("pos") or 0.0), to_next_m=to_next,
            straight_after_m=(max(0.0, to_next - 70.0) if to_next else None),
            opens_longest_straight=(k == longest_i),
            time_lost=float(c.get("time_lost") or 0.0),
            best_lap_here=c.get("best_lap_here"), recurring=bool(c.get("recurring")),
            lap_spread_s=_f(c.get("lap_spread_s")),
            apex_speed=apex_speed, apex_speed_best=best_apex or _f(c.get("apex_speed_optimal")),
            apex_error_m=float(c.get("apex_distance_error") or 0.0),
            apex_error_dir=c.get("apex_direction_error"),
            entry_speed=_f(c.get("braking_entry_speed")) or _f(c.get("entry_speed")),
            lateral_g=_f(c.get("lateral_g_max")),
            raw=c, exits=ex, phase=ph, rpm_min=rpm_min, rpm_min_best=rpm_best,
        ))
    if out and longest_i >= 0:
        session.longest_straight_m = max(0.0, (gaps[longest_i] or 0) - 70.0)
    return out
