#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Sorties de virage et relance.

Retour pilote (Auxence, octobre 2026) : le coaching parlait du freinage et des
cordes, jamais de la sortie. Or c'est souvent là que le chrono se fait : un
kart qui rentre trop fort glisse ou se cabre, le châssis « force » sur le
moteur, et la relance arrive tard. À l'inverse, attendre un peu pour tourner,
enrouler jusqu'à la corde et redresser tôt permet de remettre les gaz en ligne
droite.

Ce module ne juge rien sur une doctrine : il compare les passages DU PILOTE
dans chaque virage. Pour chaque tour, il mesure :
  - la vitesse d'entrée (pointe avant le freinage),
  - le point le plus lent (vitesse, position par rapport à la corde géométrique),
  - l'appui latéral maximal autour de la corde,
  - le régime moteur au point le plus lent (si le boîtier l'enregistre),
  - la vitesse 40 m et 80 m après le point le plus lent,
puis il cherche ce qui distingue ses meilleures sorties des moins bonnes.
Le conseil cite ses propres chiffres et le tour de référence : le pilote peut
tout vérifier dans ses données.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

EXIT_FAR_M = 80.0
EXIT_NEAR_M = 40.0
MIN_LAPS = 5


def _spearman(x: List[float], y: List[float]) -> Optional[float]:
    if len(x) < MIN_LAPS or len(set(x)) < 3 or len(set(y)) < 3:
        return None
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    if rx.std() == 0 or ry.std() == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def _value_at(d: np.ndarray, v: np.ndarray, target: float) -> Optional[float]:
    if target > d[-1] or target < d[0]:
        return None
    return float(np.interp(target, d, v))


def lap_corner_features(df: pd.DataFrame, entry_index: int, apex_index: int, exit_index: int,
                        next_entry_m: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Mesures d'un passage dans un virage, sur un tour. Indices = positions dans df."""
    if apex_index is None or apex_index < 0 or apex_index >= len(df):
        return None
    lap = df["lap_number"].iloc[apex_index] if "lap_number" in df.columns else None
    lap_df = df[df["lap_number"] == lap] if lap is not None else df
    if len(lap_df) < 30:
        return None
    d = lap_df["cumulative_distance"].to_numpy(dtype=float)
    v = lap_df["speed"].to_numpy(dtype=float)
    t = lap_df["time"].to_numpy(dtype=float) if "time" in lap_df.columns else None
    apex_d = float(df["cumulative_distance"].iloc[apex_index])

    win = (d >= apex_d - 30) & (d <= apex_d + 30)
    if win.sum() < 3:
        return None
    idx = np.where(win)[0]
    m = idx[np.argmin(v[idx])]
    m_d, m_v = float(d[m]), float(v[m])

    before = (d >= m_d - 120) & (d <= m_d)
    entry_v = float(v[before].max()) if before.any() else None

    far_target = m_d + EXIT_FAR_M
    if next_entry_m is not None and next_entry_m - m_d < EXIT_FAR_M + 10:
        far_target = None  # le virage suivant arrive avant : la vitesse à 80 m ne dit plus rien
    exit_near = _value_at(d, v, m_d + EXIT_NEAR_M)
    exit_far = _value_at(d, v, far_target) if far_target is not None else None

    # Temps mis pour parcourir la relance (du point le plus lent à +40 m / +80 m)
    relance_near_s = relance_far_s = None
    if t is not None:
        if exit_near is not None:
            relance_near_s = float(np.interp(m_d + EXIT_NEAR_M, d, t)) - float(t[m])
        if exit_far is not None:
            relance_far_s = float(np.interp(far_target, d, t)) - float(t[m])

    lat = None
    if "lateral_g" in lap_df.columns:
        around = (d >= m_d - 40) & (d <= m_d + 20)
        if around.any():
            lat = float(np.nanmax(np.abs(lap_df["lateral_g"].to_numpy(dtype=float)[around])))

    rpm_min = None
    if "rpm" in lap_df.columns:
        r = lap_df["rpm"].to_numpy(dtype=float)
        around = (d >= m_d - 10) & (d <= m_d + 10)
        if around.any() and np.nanmax(r[around]) > 1000:
            rpm_min = float(np.nanmin(r[around]))

    return {
        "lap": int(lap) if lap is not None and not pd.isna(lap) else None,
        "entry_speed": entry_v,
        "min_speed": m_v,
        "apex_shift_m": m_d - apex_d,  # positif : le point le plus lent arrive après la corde géométrique
        "lat_g": lat,
        "rpm_min": rpm_min,
        "exit_near": exit_near,
        "exit_far": exit_far,
        "relance_near_s": relance_near_s,
        "relance_far_s": relance_far_s,
    }


def analyze_corner_exits(df: pd.DataFrame, corner: Dict[str, Any], laps_used: Optional[List[int]],
                         next_corner_entry_offset: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Synthèse des sorties d'un virage sur les tours retenus."""
    rows = []
    for p in corner.get("per_lap_data") or []:
        if laps_used and p.get("lap") not in laps_used:
            continue
        try:
            next_m = None
            if next_corner_entry_offset is not None:
                next_m = float(df["cumulative_distance"].iloc[int(p["apex_index"])]) + next_corner_entry_offset
            f = lap_corner_features(df, int(p.get("entry_index", -1)), int(p["apex_index"]), int(p.get("exit_index", -1)), next_m)
        except (KeyError, ValueError, IndexError, TypeError):
            f = None
        if f and f["exit_near"] is not None:
            f["lap"] = p.get("lap", f["lap"])
            rows.append(f)
    if len(rows) < MIN_LAPS:
        return None

    key = "exit_far" if sum(1 for r in rows if r["exit_far"] is not None) >= MIN_LAPS else "exit_near"
    rows = [r for r in rows if r[key] is not None]
    rows.sort(key=lambda r: r[key], reverse=True)
    exits = [r[key] for r in rows]
    third = max(2, len(rows) // 3)
    best, worst = rows[:third], rows[-third:]

    def mean(group, k):
        vals = [r[k] for r in group if r.get(k) is not None]
        return float(np.mean(vals)) if vals else None

    levers = {}
    for k in ("entry_speed", "min_speed", "apex_shift_m", "lat_g", "rpm_min"):
        b, w = mean(best, k), mean(worst, k)
        rho = _spearman([r[k] for r in rows if r.get(k) is not None], [r[key] for r in rows if r.get(k) is not None])
        if b is not None and w is not None:
            levers[k] = {"best": round(b, 2), "worst": round(w, 2), "diff": round(b - w, 2), "rho": None if rho is None else round(rho, 2)}

    # Temps gagné sur la relance par les meilleures sorties, mesuré tour par tour.
    tkey = "relance_far_s" if key == "exit_far" else "relance_near_s"
    times = [r[tkey] for r in rows if r.get(tkey) is not None]
    best_times = [r[tkey] for r in best if r.get(tkey) is not None]
    relance_gain = None
    if len(times) >= MIN_LAPS and best_times:
        relance_gain = round(max(0.0, float(np.median(times)) - float(np.mean(best_times))), 3)

    return {
        "corner_id": corner.get("corner_id"),
        "relance_gain_s": relance_gain,
        "measure": key,
        "distance_m": EXIT_FAR_M if key == "exit_far" else EXIT_NEAR_M,
        "laps": len(rows),
        "exit_best": round(exits[0], 1),
        "exit_best_lap": rows[0]["lap"],
        "exit_median": round(float(np.median(exits)), 1),
        "exit_spread": round(exits[0] - exits[-1], 1),
        "levers": levers,
        "per_lap": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()} for r in rows],
    }


def relance_loss(ideal_lap: Optional[Dict[str, Any]], corner_id: Any) -> Dict[str, float]:
    """Temps perdu (tour idéal) sur la partie courbée du virage et sur la relance qui suit."""
    out = {"corner": 0.0, "relance": 0.0}
    for s in (ideal_lap or {}).get("sectors") or []:
        if str(s.get("corner_id")) != str(corner_id):
            continue
        out["corner" if s.get("in_corner") else "relance"] += float(s.get("loss_s") or 0)
    return {k: round(v, 3) for k, v in out.items()}


def _fmt(x: float, unit: str = "", nd: int = 0) -> str:
    s = f"{abs(x):.{nd}f}".replace(".", ",")
    return f"{s}{unit}"


def exit_advice(head: str, stats: Dict[str, Any], losses: Dict[str, float], lap_str: str = "") -> Optional[Dict[str, Any]]:
    """
    Conseil de sortie, si les sorties du pilote varient assez pour qu'on sache
    ce qui fait les bonnes. Retourne None sinon (pas de conseil inventé).
    """
    if not stats:
        return None
    gap = stats["exit_best"] - stats["exit_median"]
    # Gain mesuré sur la relance : écart de temps entre tes meilleures sorties et
    # ta sortie médiane, sur la même distance (sinon, perte du tour idéal).
    relance = stats.get("relance_gain_s")
    if relance is None:
        relance = losses.get("relance", 0.0)
    if gap < 1.5 or relance < 0.02:
        return None

    lv = stats["levers"]
    reasons: List[str] = []
    advice: List[str] = []

    def strong(k, thr):
        L = lv.get(k)
        return L if L and abs(L["diff"]) >= thr and (L["rho"] is None or abs(L["rho"]) >= 0.35) else None

    e = strong("entry_speed", 1.5)
    if e and e["diff"] < 0:
        reasons.append(f"tu entrais {_fmt(-e['diff'], ' km/h', 0)} moins vite")
        advice.append("Rentre un peu moins fort : le kart reste à plat au lieu de glisser ou de se cabrer, "
                      "le châssis ne freine plus le moteur et la relance arrive plus tôt")
    a = strong("apex_shift_m", 3.0)
    if a and a["diff"] > 0:
        reasons.append(f"ton point le plus lent arrivait {_fmt(a['diff'], ' m')} plus loin")
        advice.append("Attends un peu avant de tourner et enroule jusqu'à la corde : tu redresses plus tôt "
                      "et tu remets les gaz roues droites")
    elif a and a["diff"] < 0:
        reasons.append(f"ton point le plus lent arrivait {_fmt(-a['diff'], ' m')} plus tôt")
        advice.append("Sur ce virage, tourner plus tôt te réussit : la corde plus avancée t'ouvre la sortie")
    mn = strong("min_speed", 2.0)
    if mn and mn["diff"] > 0:
        reasons.append(f"tu gardais {_fmt(mn['diff'], ' km/h')} de plus au point le plus lent")
        advice.append("Garde de l'élan dans le virage plutôt que de casser la vitesse : enroule, "
                      "le moteur repart de plus haut")
    elif mn and mn["diff"] < 0 and not e:
        reasons.append(f"tu sacrifiais {_fmt(-mn['diff'], ' km/h')} au point le plus lent")
        advice.append("Ralentis franchement pour pivoter, puis redresse et accélère tôt : "
                      "ici, sacrifier un peu de vitesse au point de corde paie en sortie")
    g = strong("lat_g", 0.08)
    if g and g["diff"] < 0:
        reasons.append(f"le kart prenait {_fmt(-g['diff'], ' g', 2)} d'appui latéral en moins")
        advice.append("Braque moins et plus doucement : un kart qui frotte ou qui saute perd sa vitesse")
    r = strong("rpm_min", 200)
    if r and r["diff"] > 0:
        reasons.append(f"le moteur restait {_fmt(r['diff'], ' tr/min')} plus haut au point le plus lent "
                       f"({_fmt(r['best'], ' tr/min')} contre {_fmt(r['worst'], ' tr/min')})")
        if not advice:
            advice.append("Ne laisse pas le régime s'écrouler au point le plus lent : c'est lui qui fait la relance")

    measure = f"{int(stats['distance_m'])} m après le point le plus lent"
    gain_txt = (f" Sur ces {int(stats['distance_m'])} m, tes meilleures sorties te font gagner "
                f"{_fmt(relance, ' s', 2)} par rapport à ton passage habituel.") if relance >= 0.02 else ""
    if reasons:
        body = (f"{measure}, tu ressors à {_fmt(stats['exit_median'], ' km/h')} en moyenne et à "
                f"{_fmt(stats['exit_best'], ' km/h')} sur ton tour {stats['exit_best_lap']}. "
                f"Sur tes meilleures sorties, {', '.join(reasons[:2])}. "
                f"{'. '.join(advice[:2])}.{gain_txt}{lap_str}")
    else:
        body = (f"{measure}, tu ressors à {_fmt(stats['exit_median'], ' km/h')} en moyenne et à "
                f"{_fmt(stats['exit_best'], ' km/h')} sur ton tour {stats['exit_best_lap']}, sans différence nette "
                f"d'entrée ou de trajectoire entre tes passages : reprends les repères de ce tour-là "
                f"(point de braquage, moment où tu remets les gaz).{gain_txt}{lap_str}")
    return {
        "message": f"{head} — ta relance : {_fmt(gap, ' km/h', 1)} de plus à aller chercher en sortie",
        "explanation": body,
        "difficulty": "moyen",
        "impact_seconds": round(relance, 3),
        "category": "exit",
    }
