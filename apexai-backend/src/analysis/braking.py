#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Analyse de freinage.

SOURCE UNIQUE DE VÉRITÉ. Le repère posé sur la carte, la bande colorée qui le
prolonge, les chiffres du panneau « Freinages » et les conseils de coaching
sortent tous des mêmes objets produits ici. Un seul calcul, plusieurs rendus :
une pastille ne peut plus contredire sa bande, parce que la pastille EST le
premier point de la bande.

Méthode — celle qu'applique un ingénieur de piste sur MoTeC ou AiM :

1. Rééchantillonnage SPATIAL (un point tous les 2 m). Un MyChron à 25 Hz et un
   Alfano à 10 Hz produisent alors la même grille : aucun seuil ne dépend plus
   de la fréquence de l'appareil.
2. Lissage sur une longueur PHYSIQUE (12 m), jamais sur un nombre d'échantillons.
3. Accélération longitudinale par la règle de la chaîne : a = v·dv/ds. Sur une
   grille régulière en distance c'est plus stable numériquement que dv/dt.
4. Segmentation par HYSTÉRÉSIS (déclencheur de Schmitt) : on entre en freinage
   à 0,25 g, on n'en sort qu'en remontant au-dessus de 0,15 g. Deux seuils
   distincts empêchent une zone de se fragmenter quand la décélération oscille
   — le défaut des bandes précédentes — et le seuil bas reste au-dessus de la
   traînée naturelle du kart (0,05 à 0,12 g pied levé), sans quoi la bande
   avalerait la ligne droite.
5. Validation physique : un freinage doit atteindre 0,35 g crête, retirer au
   moins 6 km/h et durer au moins 4 m. Une levée de pied en ligne droite n'est
   donc plus affichée comme un freinage.

Les bornes de capacité suivent les CONDITIONS DE PISTE (`conditions.py`) : sous
la pluie un freinage à 0,55 g est bon, au sec il est mou.

Le temps perdu n'est pas une constante inventée. Pour chaque zone on compare le
temps RÉELLEMENT mis à parcourir la fenêtre « début de freinage → remise des
gaz » au temps qu'aurait pris la même fenêtre en freinant le plus tard possible,
à la décélération que le pilote a lui-même démontrée :

    t_opt = (L − d_min)/v0 + (v0 − v_min)/a_ref     avec d_min = (v0²−v_min²)/(2·a_ref)

Aucune vitesse de passage n'est supposée meilleure que celle réalisée : ce
chiffre ne mesure que le freinage et le temps mort, jamais la vitesse d'apex
(traitée ailleurs). Les deux conseils ne peuvent donc pas compter deux fois la
même seconde.
"""

from typing import Any, Dict, List, Optional, Tuple
import warnings

import numpy as np
import pandas as pd

G = 9.80665

# ─── Résolution spatiale ────────────────────────────────────────────────────
RESAMPLE_STEP_M = 2.0
SMOOTH_LENGTH_M = 12.0

# ─── Seuils de segmentation (hystérésis) ────────────────────────────────────
# Mesuré sur piste : un kart pied levé décélère déjà de 0,05 à 0,12 g sous le
# seul effet de la traînée et du roulement, tandis qu'un vrai freinage dépasse
# 0,40 g. Le seuil de SORTIE doit donc rester au-dessus de la traînée, sinon la
# bande rouge avale la moitié de la ligne droite — c'est exactement ce qui
# faisait démarrer les bandes « beaucoup trop tôt ».
BRAKE_ENTER_G = 0.25
BRAKE_EXIT_G = 0.15
# Remise des gaz : seule une accélération franche vient de l'accélérateur.
THROTTLE_ON_G = 0.12

# ─── Validation d'un événement de freinage ──────────────────────────────────
MIN_PEAK_G = 0.35
MIN_DELTA_V_KMH = 6.0
MIN_LENGTH_M = 4.0
MAX_LENGTH_M = 120.0

# Fenêtre chronométrée autour de l'apex, prolongée après lui pour inclure la
# remise des gaz : c'est là que se paie un freinage manqué.
WINDOW_EXIT_M = 15.0
WINDOW_MIN_ENTRY_M = 40.0

# ─── Capacité de freinage ───────────────────────────────────────────────────
# Bornes physiques du karting (freins arrière seuls, parfois avant en KZ).
MIN_CAPABILITY_G = 0.60
MAX_CAPABILITY_G = 1.60
CAPABILITY_PERCENTILE = 90

# Au-delà de 0,4 g latéral on considère que le kart est inscrit : le freinage
# qui continue est du trail braking, pas du freinage en ligne droite.
TRAIL_LATERAL_G = 0.40

# Temps de transfert pied-frein → pied-gaz incompressible : en dessous, le
# « temps mort » n'en est pas un.
COASTING_TOLERANCE_S = 0.15

# Nombre de points conservés pour tracer une bande sur la carte.
ZONE_POLYLINE_POINTS = 14

# Un virage n'est déclaré « zone de freinage » que si le pilote y freine sur au
# moins cette fraction des tours. Un freinage réel est récurrent ; une décélération
# isolée dans un virage rapide n'en est pas un.
MIN_LAP_COVERAGE = 0.4


# ════════════════════════════════════════════════════════════════════════════
# Grille spatiale
# ════════════════════════════════════════════════════════════════════════════

def _odd(n: int) -> int:
    return n if n % 2 == 1 else n + 1


def _smooth(y: np.ndarray, window_pts: int) -> np.ndarray:
    """Lissage Savitzky-Golay, repli sur moyenne glissante si indisponible."""
    n = len(y)
    w = _odd(max(5, min(window_pts, n - 1 if n % 2 == 0 else n - 2)))
    if w < 5 or n < 7:
        return y
    try:
        from scipy.signal import savgol_filter
        return savgol_filter(y, w, 2, mode="interp")
    except Exception:
        k = np.ones(w) / w
        return np.convolve(y, k, mode="same")


def _local_xy(lat: np.ndarray, lon: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    lat0 = float(np.nanmean(lat))
    lon0 = float(np.nanmean(lon))
    x = (lon - lon0) * 111320.0 * np.cos(np.radians(lat0))
    y = (lat - lat0) * 110540.0
    return x, y


def _build_grid(df: pd.DataFrame) -> Optional[Dict[str, np.ndarray]]:
    """
    Rééchantillonne la session sur une grille régulière en DISTANCE.

    C'est l'étape qui rend l'analyse indépendante de l'appareil : tous les
    seuils qui suivent s'appliquent à la même densité de points, que le fichier
    vienne d'un MyChron 5 à 25 Hz ou d'un Alfano à 10 Hz.
    """
    needed = ("cumulative_distance", "speed", "time")
    if any(c not in df.columns for c in needed):
        return None

    s_raw = pd.to_numeric(df["cumulative_distance"], errors="coerce").to_numpy(float)
    v_raw = pd.to_numeric(df["speed"], errors="coerce").to_numpy(float) / 3.6
    t_raw = pd.to_numeric(df["time"], errors="coerce").to_numpy(float)

    lat_col = "latitude_smooth" if "latitude_smooth" in df.columns else "latitude"
    lon_col = "longitude_smooth" if "longitude_smooth" in df.columns else "longitude"
    has_gps = lat_col in df.columns and lon_col in df.columns
    lat_raw = pd.to_numeric(df[lat_col], errors="coerce").to_numpy(float) if has_gps else None
    lon_raw = pd.to_numeric(df[lon_col], errors="coerce").to_numpy(float) if has_gps else None

    lap_raw = (
        pd.to_numeric(df["lap_number"], errors="coerce").to_numpy(float)
        if "lap_number" in df.columns else np.zeros(len(df), float)
    )

    ok = np.isfinite(s_raw) & np.isfinite(v_raw) & np.isfinite(t_raw)
    if ok.sum() < 50:
        return None

    pos = np.flatnonzero(ok)
    s = np.maximum.accumulate(s_raw[pos])
    # La distance doit être strictement croissante pour interpoler.
    keep = np.concatenate(([True], np.diff(s) > 1e-6))
    pos = pos[keep]
    s = s[keep]
    if len(s) < 50 or (s[-1] - s[0]) < 100.0:
        return None

    step = RESAMPLE_STEP_M
    grid = np.arange(s[0], s[-1], step)
    if len(grid) < 30:
        return None

    v = np.interp(grid, s, v_raw[pos])
    t = np.interp(grid, s, t_raw[pos])
    # Le numéro de tour est une étiquette : plus proche voisin, jamais interpolé.
    src = np.clip(np.searchsorted(s, grid, side="left"), 0, len(s) - 1)
    lap = lap_raw[pos][src]
    orig_pos = pos[src]

    win = int(round(SMOOTH_LENGTH_M / step))
    v_s = np.maximum(_smooth(v, win), 0.0)

    # a = v·dv/ds — exact, et bien plus stable qu'une dérivée temporelle sur un
    # signal GPS bruité.
    ax = v_s * np.gradient(v_s, grid)

    if has_gps:
        lat = np.interp(grid, s, lat_raw[pos])
        lon = np.interp(grid, s, lon_raw[pos])
        x, y = _local_xy(lat, lon)
        x_s, y_s = _smooth(x, win), _smooth(y, win)
        dx, dy = np.gradient(x_s, grid), np.gradient(y_s, grid)
        ddx, ddy = np.gradient(dx, grid), np.gradient(dy, grid)
        denom = np.power(dx * dx + dy * dy, 1.5)
        with np.errstate(invalid="ignore", divide="ignore"):
            kappa = np.abs(dx * ddy - dy * ddx) / np.where(denom > 1e-9, denom, np.nan)
        kappa = np.nan_to_num(kappa, nan=0.0, posinf=0.0)
        ay = v_s * v_s * kappa
    else:
        lat = lon = np.full(len(grid), np.nan)
        ay = np.zeros(len(grid))

    return {
        "s": grid, "v": v_s, "t": t, "ax": ax, "ay": ay,
        "lat": lat, "lon": lon, "lap": lap, "orig_pos": orig_pos,
        "step": np.array([step]),
    }


# ════════════════════════════════════════════════════════════════════════════
# Segmentation
# ════════════════════════════════════════════════════════════════════════════

def _segment(ax: np.ndarray) -> List[Tuple[int, int]]:
    """
    Zones de freinage par hystérésis (déclencheur de Schmitt).

    Un point sous le seuil d'ENTRÉE amorce la zone ; on l'étend ensuite de part
    et d'autre tant que la décélération reste sous le seuil de SORTIE, plus bas.
    Deux seuils distincts : c'est la seule façon d'obtenir une bande continue
    quand le signal oscille, au lieu d'un peigne de bandes fragmentées.
    """
    enter = -BRAKE_ENTER_G * G
    exit_ = -BRAKE_EXIT_G * G
    n = len(ax)
    below_exit = ax < exit_
    out: List[Tuple[int, int]] = []
    i = 0
    while i < n:
        if ax[i] < enter:
            a = i
            while a > 0 and below_exit[a - 1]:
                a -= 1
            b = i
            while b < n - 1 and below_exit[b + 1]:
                b += 1
            if out and a <= out[-1][1]:
                out[-1] = (out[-1][0], max(out[-1][1], b))
            else:
                out.append((a, b))
            i = b + 1
        else:
            i += 1
    return out


def _throttle_on(ax: np.ndarray, start: int) -> int:
    """Premier point de remise des gaz après la fin du freinage."""
    thr = THROTTLE_ON_G * G
    n = len(ax)
    for i in range(start, n):
        if ax[i] > thr:
            return i
    return min(start, n - 1)


def _polyline(lat: np.ndarray, lon: np.ndarray, a: int, b: int) -> Dict[str, List[float]]:
    """Tracé compact d'une zone, prêt à être dessiné sur la carte."""
    if b <= a or not np.isfinite(lat[a:b + 1]).any():
        return {"lat": [], "lon": []}
    idx = np.unique(np.linspace(a, b, min(ZONE_POLYLINE_POINTS, b - a + 1)).astype(int))
    return {
        "lat": [round(float(lat[i]), 7) for i in idx],
        "lon": [round(float(lon[i]), 7) for i in idx],
    }


# ════════════════════════════════════════════════════════════════════════════
# Événements
# ════════════════════════════════════════════════════════════════════════════

def _detect_events(grid: Dict[str, np.ndarray]) -> List[Dict[str, Any]]:
    s, v, t, ax, ay = grid["s"], grid["v"], grid["t"], grid["ax"], grid["ay"]
    lat, lon, lap = grid["lat"], grid["lon"], grid["lap"]

    events: List[Dict[str, Any]] = []
    for a, b in _segment(ax):
        length = float(s[b] - s[a])
        if length < MIN_LENGTH_M or length > MAX_LENGTH_M:
            continue
        seg = ax[a:b + 1]
        peak_g = float(-np.min(seg) / G)
        if peak_g < MIN_PEAK_G:
            continue
        v_in = float(v[a])
        v_out = float(np.min(v[a:b + 1]))
        if (v_in - v_out) * 3.6 < MIN_DELTA_V_KMH:
            continue

        # Fenêtre complète : freinage + temps mort, jusqu'à la remise des gaz.
        thr = _throttle_on(ax, b)
        peak_pos = a + int(np.argmin(seg))

        # Part du freinage réalisée kart déjà inscrit (trail braking).
        lat_g = ay[a:b + 1] / G
        trail = float(np.mean(lat_g > TRAIL_LATERAL_G)) if len(lat_g) else 0.0

        coast_s = float(max(0.0, t[thr] - t[b]))
        events.append({
            "i_start": int(a),
            "i_peak": int(peak_pos),
            "i_end": int(b),
            "i_throttle": int(thr),
            "lap": int(lap[a]) if np.isfinite(lap[a]) else -1,
            "start_s": float(s[a]),
            "end_s": float(s[b]),
            "throttle_s": float(s[thr]),
            "length_m": length,
            "duration_s": float(max(0.0, t[b] - t[a])),
            "v_in_kmh": v_in * 3.6,
            "v_out_kmh": v_out * 3.6,
            "delta_v_kmh": (v_in - v_out) * 3.6,
            "peak_g": peak_g,
            "avg_g": float(-np.mean(seg) / G),
            # Distance mise à atteindre la décélération maximale : mesure la
            # vivacité de l'attaque de frein.
            "build_up_m": float(s[peak_pos] - s[a]),
            "trail_ratio": trail,
            "coasting_s": coast_s,
            "coasting_m": float(max(0.0, s[thr] - s[b])),
            "window_time_s": float(max(0.0, t[thr] - t[a])),
            "window_length_m": float(max(0.0, s[thr] - s[a])),
            "start_lat": float(lat[a]) if np.isfinite(lat[a]) else None,
            "start_lon": float(lon[a]) if np.isfinite(lon[a]) else None,
            "zone": _polyline(lat, lon, a, b),
            "coasting_zone": _polyline(lat, lon, b, thr) if coast_s > COASTING_TOLERANCE_S else {"lat": [], "lon": []},
        })
    return events


# ════════════════════════════════════════════════════════════════════════════
# Capacité de freinage démontrée
# ════════════════════════════════════════════════════════════════════════════

def _capability_g(events: List[Dict[str, Any]], conditions=None) -> float:
    """
    Décélération que le pilote a RÉELLEMENT démontrée (en g).

    Référence honnête : on ne lui demande jamais de faire mieux que son propre
    meilleur freinage. Une constante théorique donnerait un objectif inatteignable
    en Mini et beaucoup trop tendre en KZ.

    Les bornes suivent les conditions de piste : un plancher « sec » de 0,60 g
    appliqué à une séance sous la pluie ferait passer un freinage correct pour
    un freinage mou.
    """
    lo = conditions.braking_min_g if conditions is not None else MIN_CAPABILITY_G
    # Le PLAFOND reste la limite physique du karting, jamais l'attente liée à la
    # météo : si le pilote a réellement freiné à 1,2 g, on ne va pas lui
    # répondre que la pluie l'en empêchait. La mesure prime sur la déclaration.
    hi = MAX_CAPABILITY_G
    peaks = [e["peak_g"] for e in events if np.isfinite(e["peak_g"])]
    if len(peaks) < 3:
        return float(np.clip(0.9, lo, hi))
    return float(np.clip(np.percentile(peaks, CAPABILITY_PERCENTILE), lo, hi))


def _theoretical_min_distance(v0_kmh: float, v1_kmh: float, a_ref_g: float) -> float:
    """
    Distance de freinage minimale physique : d = (v0² − v1²) / (2a).

    Borne INFÉRIEURE, affichée comme telle. Elle sert à dire « la physique
    autorise 28 m », jamais à promettre un gain : le chiffre annoncé au pilote
    vient toujours d'un passage qu'il a réellement réalisé.
    """
    v0, v1 = v0_kmh / 3.6, v1_kmh / 3.6
    a = max(0.1, a_ref_g * G)
    if v0 <= v1:
        return 0.0
    return float((v0 * v0 - v1 * v1) / (2.0 * a))


# ════════════════════════════════════════════════════════════════════════════
# Rattachement aux virages
# ════════════════════════════════════════════════════════════════════════════

def _project_missing_apexes(
    df: pd.DataFrame,
    apexes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Complète les apex manquants tour par tour.

    La détection de virages ne retrouve pas systématiquement chaque apex sur
    chaque tour. Or un virage manquant décale tout : le freinage qui lui était
    destiné se raccroche au virage SUIVANT, et l'on voit apparaître un « V8 à
    106 m » qui est en réalité le freinage du V7.

    Un virage ne bougeant pas de place sur le circuit, on fixe sa position
    relative (fraction du tour, robuste aux petites variations de longueur) et
    on la projette sur tous les tours. Chaque virage est alors évalué sur tous
    les tours, ou sur aucun.
    """
    if "lap_number" not in df.columns or "cumulative_distance" not in df.columns:
        return apexes
    dist = pd.to_numeric(df["cumulative_distance"], errors="coerce")
    lap = pd.to_numeric(df["lap_number"], errors="coerce")
    spans: Dict[int, Tuple[float, float]] = {}
    for ln, sub in dist.groupby(lap):
        s = sub.dropna()
        if len(s) < 20:
            continue
        lo, hi = float(s.min()), float(s.max())
        if hi - lo > 150.0:
            spans[int(ln)] = (lo, hi - lo)
    if len(spans) < 2:
        return apexes

    by_corner: Dict[int, List[Dict[str, Any]]] = {}
    for a in apexes:
        by_corner.setdefault(a["corner_id"], []).append(a)

    out = list(apexes)
    for cid, found in by_corner.items():
        seen = {a["lap"] for a in found}
        fracs = [
            (a["apex_s"] - spans[a["lap"]][0]) / spans[a["lap"]][1]
            for a in found if a["lap"] in spans
        ]
        fracs = [f for f in fracs if 0.0 <= f <= 1.0]
        if len(fracs) < 2:
            continue
        frac = float(np.median(fracs))
        for ln, (lo, length) in spans.items():
            if ln in seen:
                continue
            out.append({"corner_id": cid, "lap": ln,
                        "apex_s": lo + frac * length, "projected": True})
    return out


def _apexes_by_lap(
    df: pd.DataFrame,
    grid: Dict[str, np.ndarray],
    corner_details: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Position (tour, virage, distance cumulée) de chaque apex.

    On réutilise les apex de la détection de virages : c'est la même vérité que
    la carte et que les conseils. Sans elle (tests unitaires), on retombe sur la
    colonne `corner_id` et le point le plus lent de chaque segment.
    """
    out: List[Dict[str, Any]] = []
    dist = pd.to_numeric(df["cumulative_distance"], errors="coerce")

    if corner_details:
        for c in corner_details:
            cid = c.get("id", c.get("corner_id"))
            if cid is None:
                continue
            for pl in (c.get("per_lap_data") or []):
                label = pl.get("apex_index")
                if label is None or label not in dist.index:
                    continue
                d = dist.loc[label]
                if pd.isna(d):
                    continue
                out.append({"corner_id": int(cid), "lap": int(pl.get("lap", -1)),
                            "apex_s": float(d)})
        if out:
            out = _project_missing_apexes(df, out)
            out.sort(key=lambda a: a["apex_s"])
            return out

    if "corner_id" not in df.columns or "speed" not in df.columns:
        return out
    cid = pd.to_numeric(df["corner_id"], errors="coerce")
    lap = (pd.to_numeric(df["lap_number"], errors="coerce")
           if "lap_number" in df.columns else pd.Series(0, index=df.index))
    speed = pd.to_numeric(df["speed"], errors="coerce")
    mask = cid.notna()
    if not mask.any():
        return out
    # Un segment = points contigus partageant le même virage sur le même tour.
    grp = ((cid != cid.shift()) | (lap != lap.shift())).cumsum()[mask]
    for _, sub in df[mask].groupby(grp):
        sp = speed.loc[sub.index]
        if sp.isna().all():
            continue
        label = sp.idxmin()
        d = dist.loc[label]
        if pd.isna(d):
            continue
        out.append({"corner_id": int(cid.loc[label]), "lap": int(lap.loc[label] or 0),
                    "apex_s": float(d)})
    out.sort(key=lambda a: a["apex_s"])
    return out


def _attach(events: List[Dict[str, Any]], apexes: List[Dict[str, Any]]) -> None:
    """
    Rattache chaque freinage au virage qu'il prépare.

    Règle physique : l'apex visé est le PREMIER apex situé au-delà du début du
    freinage. On ne peut pas freiner pour le virage 8 avant d'avoir passé le 7 —
    c'est cette contrainte qui garantit que les repères restent dans l'ordre du
    tour sur la carte.
    """
    if not apexes:
        return
    apex_s = np.array([a["apex_s"] for a in apexes])
    for e in events:
        j = int(np.searchsorted(apex_s, e["start_s"], side="left"))
        if j >= len(apexes):
            continue
        cand = apexes[j]
        gap = cand["apex_s"] - e["end_s"]
        # L'apex doit suivre le freinage de près : au-delà d'une ligne droite
        # entière, ce freinage ne prépare pas ce virage.
        if -MAX_LENGTH_M <= gap <= 60.0:
            e["corner_id"] = cand["corner_id"]
            e["apex_s"] = cand["apex_s"]
            e["distance_to_apex_m"] = float(cand["apex_s"] - e["start_s"])
            # Le freinage appartient au tour du virage qu'il prépare, même
            # lorsqu'il commence avant la ligne de chronométrage.
            e["lap"] = int(cand["lap"])


# ════════════════════════════════════════════════════════════════════════════
# API publique
# ════════════════════════════════════════════════════════════════════════════

def _representative_laps(df: pd.DataFrame) -> set:
    """
    Tours exploitables — exactement ceux du tour idéal et des conseils.

    Réutiliser cette source unique évite qu'un écran annonce « 11 tours » et un
    autre « 8 » pour la même session.
    """
    try:
        from src.analysis.ideal_lap import _valid_lap_numbers
        laps = set(int(x) for x in _valid_lap_numbers(df))
        if laps:
            return laps
    except Exception:
        pass
    if "lap_number" in df.columns:
        return set(int(x) for x in pd.to_numeric(df["lap_number"], errors="coerce").dropna().unique())
    return set()


def _fastest_lap(df: pd.DataFrame) -> Optional[int]:
    """
    Meilleur tour, recalculé ici plutôt que lu dans `df.attrs`.

    L'analyse de freinage tourne tôt dans le pipeline, avant que le meilleur
    tour n'y soit inscrit : dépendre de l'ordre des étapes rendrait le résultat
    différent selon le point d'appel.
    """
    if "lap_number" not in df.columns or "time" not in df.columns:
        return None
    valid = _representative_laps(df)
    t = pd.to_numeric(df["time"], errors="coerce")
    best, best_t = None, float("inf")
    for ln, sub in t.groupby(pd.to_numeric(df["lap_number"], errors="coerce")):
        if valid and int(ln) not in valid:
            continue
        s = sub.dropna()
        if len(s) < 20:
            continue
        lt = float(s.max() - s.min())
        if 10.0 < lt < best_t:
            best, best_t = int(ln), lt
    return best


# Un freinage n'est jugé « trop mou » que si le virage demande vraiment de
# ralentir : exiger 0,9 g dans une courbe qui ne coûte que 8 km/h n'aurait
# aucun sens et décrédibiliserait l'analyse.
SOFT_MIN_DELTA_V_KMH = 15.0
SOFT_PEAK_RATIO = 0.75

# Seuils de significativité. Un écart en deçà relève du bruit de mesure, pas du
# pilotage.
POINT_SIGNIFICANT_M = 3.0
COASTING_SIGNIFICANT_S = 0.15
SPREAD_SIGNIFICANT_M = 6.0
# Filet de sécurité : au-delà, le temps mort est anormal quoi qu'il arrive.
COASTING_ABSOLUTE_S = 0.80


def _verdict(
    delta_m: float,
    peak_g: float,
    capability_g: float,
    delta_v_kmh: float,
    coasting_excess_s: float,
    coasting_s: float,
    spread_m: float,
) -> str:
    """
    Défaut dominant du freinage.

    Deux principes.

    1. Les verdicts DÉCRIVENT ce que le pilote a fait différemment sur son
       meilleur passage ; ils ne le jugent pas. « Freiner plus tôt » n'est pas
       une faute : si son tour le plus rapide freinait plus tôt ici, c'est cela
       qu'il faut reproduire, et lui dire l'inverse le ferait ralentir.
    2. Tout se mesure PAR RAPPORT À LUI-MÊME sur ce virage. En karting, un
       temps mort de 0,4 s entre frein et gaz est normal dans une épingle : le
       juger sur un seuil absolu ferait ressortir le même reproche sur tous les
       virages, et un défaut signalé partout n'aide personne.

    L'écart le plus marqué l'emporte, chacun rapporté à son propre seuil.
    """
    if (peak_g < SOFT_PEAK_RATIO * capability_g
            and delta_v_kmh >= SOFT_MIN_DELTA_V_KMH):
        return "soft"
    if coasting_s >= COASTING_ABSOLUTE_S:
        return "coasting"

    point_score = abs(delta_m) / POINT_SIGNIFICANT_M
    coast_score = coasting_excess_s / COASTING_SIGNIFICANT_S
    if max(point_score, coast_score) >= 1.0:
        if coast_score > point_score:
            return "coasting"
        return "brake_later" if delta_m > 0 else "brake_earlier"
    if spread_m >= SPREAD_SIGNIFICANT_M:
        return "inconsistent"
    return "optimal"


def analyze_braking(
    df: pd.DataFrame,
    corner_details: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Analyse complète du freinage sur la session.

    Returns:
        {
          'capability_g': décélération démontrée par le pilote,
          'by_corner':   {corner_id: agrégat + repère de référence},
          'by_lap':      {lap_number: [zones à tracer]},
          'events':      liste à plat (tests / diagnostics),
        }
    """
    empty = {"capability_g": 0.0, "by_corner": {}, "by_lap": {}, "events": []}
    try:
        grid = _build_grid(df)
        if grid is None:
            return empty

        events = _detect_events(grid)
        if not events:
            return empty

        apexes = _apexes_by_lap(df, grid, corner_details)
        _attach(events, apexes)
        events = [e for e in events if "corner_id" in e]
        if not events:
            return empty

        from src.analysis.conditions import get_conditions
        conditions = get_conditions(df)
        a_ref = _capability_g(events, conditions)

        # Un seul freinage principal par (tour, virage) : celui qui retire le
        # plus de vitesse. Les autres sont des retouches de frein — une info
        # utile, pas une deuxième pastille.
        primary: Dict[Tuple[int, int], Dict[str, Any]] = {}
        extras: Dict[Tuple[int, int], int] = {}
        for e in events:
            key = (e["lap"], e["corner_id"])
            if key not in primary or e["delta_v_kmh"] > primary[key]["delta_v_kmh"]:
                if key in primary:
                    extras[key] = extras.get(key, 0) + 1
                primary[key] = e
            else:
                extras[key] = extras.get(key, 0) + 1

        by_corner_events: Dict[int, List[Dict[str, Any]]] = {}
        for (lap, cid), e in primary.items():
            e["double_brake"] = extras.get((lap, cid), 0) > 0
            by_corner_events.setdefault(cid, []).append(e)

        # ── Un virage de freinage se freine à TOUS les tours ─────────────────
        # Un virage rapide pris à plat produit parfois, sur un ou deux tours,
        # une petite décélération fortuite. L'afficher comme zone de freinage
        # ferait mentir la carte. On exige donc que le freinage soit récurrent.
        n_laps = len({a["lap"] for a in apexes})
        min_laps = max(2, int(np.ceil(MIN_LAP_COVERAGE * n_laps))) if n_laps else 2
        by_corner_events = {c: e for c, e in by_corner_events.items() if len(e) >= min_laps}
        if not by_corner_events:
            return empty
        kept = set(by_corner_events)
        primary = {k: v for k, v in primary.items() if k[1] in kept}
        events = [e for e in events if e["corner_id"] in kept]

        # ── Chronométrage de la fenêtre de freinage ─────────────────────────
        # Pour chaque virage on fixe UNE fenêtre spatiale (identique à tous les
        # tours) et on mesure le temps réellement mis à la parcourir. Comparer
        # deux tours sur la même portion de piste ne suppose aucun modèle : le
        # gain annoncé est un temps que le pilote a déjà réalisé.
        gs, gt = grid["s"], grid["t"]
        for cid, evs in by_corner_events.items():
            pts = [e.get("distance_to_apex_m", 0.0) for e in evs]
            w = max(WINDOW_MIN_ENTRY_M, float(np.max(pts)) + 10.0)
            for e in evs:
                s0 = e["apex_s"] - w
                s1 = e["apex_s"] + WINDOW_EXIT_M
                if s0 < gs[0] or s1 > gs[-1]:
                    e["window_measured_s"] = None
                    continue
                e["window_measured_s"] = float(np.interp(s1, gs, gt) - np.interp(s0, gs, gt))
            e_ok = [e for e in evs if e.get("window_measured_s")]
            best_t = min((e["window_measured_s"] for e in e_ok), default=None)
            for e in evs:
                wm = e.get("window_measured_s")
                e["time_lost_s"] = round(max(0.0, wm - best_t), 3) if (wm and best_t) else 0.0

        by_lap: Dict[int, List[Dict[str, Any]]] = {}
        for (lap, cid), e in primary.items():
            zone = {
                "corner_id": cid,
                "kind": "braking",
                "lat": e["zone"]["lat"],
                "lon": e["zone"]["lon"],
                # La pastille EST le premier point de la bande : même objet,
                # donc impossible qu'elles se contredisent à l'écran.
                "start_lat": e["zone"]["lat"][0] if e["zone"]["lat"] else e["start_lat"],
                "start_lon": e["zone"]["lon"][0] if e["zone"]["lon"] else e["start_lon"],
                "peak_g": round(e["peak_g"], 2),
                "length_m": round(e["length_m"], 1),
                "duration_s": round(e["duration_s"], 2),
                "distance_to_apex_m": round(e.get("distance_to_apex_m", 0.0), 1),
                "entry_speed_kmh": round(e["v_in_kmh"], 1),
                "min_speed_kmh": round(e["v_out_kmh"], 1),
                "coasting_s": round(e["coasting_s"], 2),
                "coasting_lat": e["coasting_zone"]["lat"],
                "coasting_lon": e["coasting_zone"]["lon"],
                "time_lost_s": float(e.get("time_lost_s", 0.0)),
                "double_brake": bool(e["double_brake"]),
            }
            by_lap.setdefault(int(lap), []).append(zone)
        for lap in by_lap:
            by_lap[lap].sort(key=lambda z: z["corner_id"])

        # ── Agrégat par virage ──────────────────────────────────────────────
        # Les chiffres publiés ne portent que sur les tours REPRÉSENTATIFS —
        # les mêmes que ceux du tour idéal et des conseils. Un tour de sortie
        # de stand fausserait la régularité du point de freinage. Les zones
        # dessinées sur la carte, elles, restent disponibles pour tous les tours.
        valid_laps = _representative_laps(df)
        best_lap = df.attrs.get("best_lap_number") or _fastest_lap(df)
        by_corner: Dict[int, Dict[str, Any]] = {}
        for cid, all_evs in by_corner_events.items():
            evs = [e for e in all_evs if e["lap"] in valid_laps] or all_evs
            pts = np.array([e.get("distance_to_apex_m", 0.0) for e in evs], float)
            ref = next((e for e in evs if best_lap is not None and e["lap"] == int(best_lap)), None)
            if ref is None:
                # À défaut du meilleur tour : le freinage médian, jamais un extrême.
                ref = evs[int(np.argsort(pts)[len(pts) // 2])]

            # RÉFÉRENCE DU PILOTE : son passage le plus rapide sur cette même
            # portion de piste. Pas un modèle, pas une moyenne du plateau — un
            # tour qu'il a signé lui-même, donc indiscutable et reproductible.
            timed = [e for e in evs if e.get("window_measured_s")]
            best = min(timed, key=lambda e: e["window_measured_s"]) if timed else ref

            delta = float(ref.get("distance_to_apex_m", 0.0) - best.get("distance_to_apex_m", 0.0))
            peak_session = float(np.max([e["peak_g"] for e in evs]))
            d_theo = _theoretical_min_distance(ref["v_in_kmh"], ref["v_out_kmh"], a_ref)
            spread = float(np.std(pts)) if len(pts) > 1 else 0.0
            coast_excess = max(0.0, ref["coasting_s"] - best["coasting_s"])
            verdict = _verdict(delta, ref["peak_g"], a_ref, ref["delta_v_kmh"],
                               coast_excess, ref["coasting_s"], spread)

            by_corner[int(cid)] = {
                "corner_id": int(cid),
                "laps": len(evs),
                "reference_lap": int(ref["lap"]),
                "braking_lat": ref["zone"]["lat"][0] if ref["zone"]["lat"] else ref["start_lat"],
                "braking_lon": ref["zone"]["lon"][0] if ref["zone"]["lon"] else ref["start_lon"],
                "braking_point_distance": round(float(ref.get("distance_to_apex_m", 0.0)), 1),
                "braking_point_optimal": round(float(best.get("distance_to_apex_m", 0.0)), 1),
                "braking_delta": round(delta, 1),
                "braking_verdict": verdict,
                "braking_length_m": round(ref["length_m"], 1),
                "braking_duration_s": round(ref["duration_s"], 2),
                "braking_peak_g": round(ref["peak_g"], 2),
                "braking_avg_g": round(ref["avg_g"], 2),
                "braking_build_up_m": round(ref["build_up_m"], 1),
                "braking_entry_speed": round(ref["v_in_kmh"], 1),
                "braking_min_speed": round(ref["v_out_kmh"], 1),
                "braking_delta_v": round(ref["delta_v_kmh"], 1),
                "braking_theoretical_min_m": round(d_theo, 1),
                "trail_braking_ratio": round(ref["trail_ratio"], 2),
                "coasting_s": round(ref["coasting_s"], 2),
                "coasting_m": round(ref["coasting_m"], 1),
                "coasting_best_s": round(best["coasting_s"], 2),
                "coasting_excess_s": round(coast_excess, 2),
                "braking_time_lost": float(ref.get("time_lost_s", 0.0)),
                # Dispersion du point de freinage d'un tour à l'autre : le vrai
                # marqueur du niveau. Un pilote confirmé tient 2–3 m.
                "braking_consistency_m": round(spread, 1),
                "braking_best_lap": int(best["lap"]),
                "braking_best_point_m": round(float(best.get("distance_to_apex_m", 0.0)), 1),
                "braking_best_min_speed": round(best["v_out_kmh"], 1),
                "braking_best_peak_g": round(best["peak_g"], 2),
                "braking_corner_peak_g": round(peak_session, 2),
                "braking_capability_g": round(a_ref, 2),
                "double_brake_laps": int(sum(1 for e in evs if e["double_brake"])),
            }

        return {
            "capability_g": round(a_ref, 2),
            "by_corner": by_corner,
            "by_lap": by_lap,
            "events": events,
        }
    except Exception as exc:  # pragma: no cover - garde-fou pipeline
        warnings.warn(f"analyze_braking: {exc}")
        return empty


def get_braking_analysis(
    df: pd.DataFrame,
    corner_details: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Version mise en cache sur le DataFrame : un seul calcul par session."""
    cached = df.attrs.get("_braking_analysis")
    if cached is not None:
        return cached
    result = analyze_braking(df, corner_details)
    df.attrs["_braking_analysis"] = result
    return result


def phase_labels(lap_df: pd.DataFrame, analysis: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Phase de pilotage en chaque point d'un tour : « braking », « coasting » ou
    « acceleration ».

    Dérivée des MÊMES zones que les bandes de la carte : la couleur de la trace
    et la bande de freinage ne peuvent donc pas se contredire.
    """
    n = len(lap_df)
    if n == 0 or "cumulative_distance" not in lap_df.columns:
        return []
    s = pd.to_numeric(lap_df["cumulative_distance"], errors="coerce").to_numpy(float)
    labels = ["coasting"] * n

    events: List[Dict[str, Any]] = []
    if analysis:
        lap_vals = pd.to_numeric(lap_df.get("lap_number"), errors="coerce") if "lap_number" in lap_df.columns else None
        lap_no = int(lap_vals.iloc[0]) if lap_vals is not None and len(lap_vals) and pd.notna(lap_vals.iloc[0]) else None
        events = [e for e in analysis.get("events", []) if lap_no is None or e["lap"] == lap_no]

    if events:
        for e in events:
            m = (s >= e["start_s"]) & (s <= e["end_s"])
            for i in np.flatnonzero(m):
                labels[int(i)] = "braking"
        # Accélération : après la remise des gaz, jusqu'au freinage suivant.
        starts = sorted(e["throttle_s"] for e in events)
        ends = sorted(e["start_s"] for e in events)
        for st in starts:
            nxt = next((x for x in ends if x > st), float("inf"))
            m = (s > st) & (s < nxt)
            for i in np.flatnonzero(m):
                labels[int(i)] = "acceleration"
        return labels

    # Repli sans analyse disponible : seuils physiques identiques.
    if "speed" not in lap_df.columns or "time" not in lap_df.columns:
        return labels
    v = pd.to_numeric(lap_df["speed"], errors="coerce").to_numpy(float) / 3.6
    t = pd.to_numeric(lap_df["time"], errors="coerce").to_numpy(float)
    if n < 3 or not np.isfinite(t).any():
        return labels
    a = np.gradient(np.nan_to_num(v), t) / G
    return ["braking" if x < -BRAKE_ENTER_G else "acceleration" if x > THROTTLE_ON_G else "coasting"
            for x in a]
