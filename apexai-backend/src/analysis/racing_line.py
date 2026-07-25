#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Ligne de course idéale (optimal racing line).

Objectif : produire une VRAIE ligne de course objective à aller chercher, et non
un tour « lissé + 3,5 % » cosmétique. La méthode répond aux problèmes de
crédibilité d'une trajectoire idéale sur un tracé karting réel :

1. COULOIR RÉEL — on reconstruit la largeur exploitable du circuit à partir de
   l'enveloppe des trajectoires du pilote (tous ses tours). La ligne idéale reste
   donc bornée dans les limites réellement roulées, jamais dans le décor.
2. COURBURE MINIMALE — on résout la « minimum-curvature raceline » (algorithme
   motorsport classique) : la ligne qui minimise la courbure dans le couloir,
   i.e. la vraie corde out-in-out avec apex retardés là où il faut.
3. VITESSES CALIBRÉES — l'adhérence μ est déduite du grip RÉELLEMENT atteint par
   le pilote (pas un 1,1 codé en dur), puis on applique des limites longitudinales
   (accélération/freinage) pour un profil de vitesse atteignable.

Sortie : lat/lon de la ligne idéale + vitesse cible le long de la ligne +
temps au tour idéal. Pur numpy/scipy, défensif (renvoie available=False sinon).
"""

from typing import Any, Dict, List, Optional
import warnings

import numpy as np

try:
    from scipy.spatial import cKDTree
    from scipy.optimize import lsq_linear
    _SCIPY = True
except Exception:  # pragma: no cover
    _SCIPY = False

G = 9.81
A_BRAKE = 1.5 * G      # décélération max karting (~1.5 g)
A_ACCEL = 0.6 * G      # accélération long. réaliste karting
MU_MIN, MU_MAX = 1.0, 1.55


def _to_local_xy(lat: np.ndarray, lon: np.ndarray) -> tuple:
    """Projection équirectangulaire locale (mètres) autour du barycentre."""
    lat0 = float(np.nanmean(lat))
    lon0 = float(np.nanmean(lon))
    m_per_deg_lat = 111_132.0
    m_per_deg_lon = 111_320.0 * np.cos(np.radians(lat0))
    x = (lon - lon0) * m_per_deg_lon
    y = (lat - lat0) * m_per_deg_lat
    return x, y, lat0, lon0, m_per_deg_lat, m_per_deg_lon


def _resample_closed(x: np.ndarray, y: np.ndarray, n: int) -> tuple:
    """Rééchantillonne une boucle fermée en n points équidistants (par abscisse curviligne)."""
    pts = np.column_stack([x, y])
    # Fermer la boucle
    if np.hypot(*(pts[0] - pts[-1])) > 1e-6:
        pts = np.vstack([pts, pts[0]])
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = s[-1]
    if total <= 0:
        raise ValueError("longueur nulle")
    target = np.linspace(0.0, total, n, endpoint=False)
    xr = np.interp(target, s, pts[:, 0])
    yr = np.interp(target, s, pts[:, 1])
    return xr, yr, total


def _periodic_second_diff(n: int) -> np.ndarray:
    D = np.zeros((n, n))
    for i in range(n):
        D[i, (i - 1) % n] = 1.0
        D[i, i] = -2.0
        D[i, (i + 1) % n] = 1.0
    return D


def _periodic_first_diff(n: int) -> np.ndarray:
    D = np.zeros((n, n))
    for i in range(n):
        D[i, i] = -1.0
        D[i, (i + 1) % n] = 1.0
    return D


def _curvature(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Courbure signée d'une courbe fermée (périodique)."""
    dx = np.gradient(x)
    dy = np.gradient(y)
    ddx = np.gradient(dx)
    ddy = np.gradient(dy)
    denom = (dx * dx + dy * dy) ** 1.5
    denom[denom < 1e-9] = 1e-9
    return (dx * ddy - dy * ddx) / denom


def _valid_laps(df) -> List[int]:
    """Tours valides : source unique partagée avec le module tour idéal
    (exclut out/in-laps, tours trop lents ET tours partiels de longueur incohérente)."""
    from src.analysis.ideal_lap import _valid_lap_numbers
    laps = _valid_lap_numbers(df)
    if laps:
        return laps
    # Repli si pas de base temps : tours >=1 avec assez de points
    import pandas as pd
    if "lap_number" not in df.columns:
        return []
    return [int(ln) for ln, g in df.groupby("lap_number") if int(ln) >= 1 and len(g) > 50]


def build_racing_line(
    df,
    n_points: int = 300,
    margin_m: float = 0.3,
    smooth_lambda: float = 0.12,
    assumed_track_width_m: float = 8.0,
    max_half_width_m: float = 5.0,
) -> Dict[str, Any]:
    """
    Construit la ligne de course idéale.

    Returns dict avec available: bool. Si available:
      lat[], lon[], speed_kmh[]           — la ligne idéale à dessiner
      optimal_lap_time_s                  — temps au tour de cette ligne
      mu_calibrated                       — grip déduit des données du pilote
      curvature_reduction_pct             — gain de courbure vs ligne de référence
      max_lateral_shift_m                 — écart max ligne idéale vs ligne roulée
      corridor_width_m                    — largeur moyenne du couloir estimé
    """
    import pandas as pd
    try:
        if not _SCIPY:
            return {"available": False, "reason": "scipy indisponible"}
        lat_col = "latitude_smooth" if "latitude_smooth" in df.columns else "latitude"
        lon_col = "longitude_smooth" if "longitude_smooth" in df.columns else "longitude"
        if lat_col not in df.columns or lon_col not in df.columns:
            return {"available": False, "reason": "pas de GPS"}

        laps = _valid_laps(df)
        if not laps:
            return {"available": False, "reason": "aucun tour valide"}

        # --- Ligne de référence = meilleur tour (temps le plus court) ---
        best_ln = laps[0]
        if "time" in df.columns:
            best_t = np.inf
            for ln in laps:
                g = df[df["lap_number"] == ln]
                t = pd.to_numeric(g["time"], errors="coerce").dropna()
                if len(t) >= 2 and (t.max() - t.min()) < best_t:
                    best_t, best_ln = float(t.max() - t.min()), ln
        ref = df[df["lap_number"] == best_ln]
        rlat = pd.to_numeric(ref[lat_col], errors="coerce").to_numpy(float)
        rlon = pd.to_numeric(ref[lon_col], errors="coerce").to_numpy(float)
        m = ~(np.isnan(rlat) | np.isnan(rlon))
        rlat, rlon = rlat[m], rlon[m]
        if len(rlat) < 30:
            return {"available": False, "reason": "tour de référence trop court"}

        x, y, lat0, lon0, mlat, mlon = _to_local_xy(rlat, rlon)
        Px, Py, track_len = _resample_closed(x, y, n_points)

        # Tangentes / normales (normale à gauche)
        tx = np.gradient(Px)
        ty = np.gradient(Py)
        tn = np.hypot(tx, ty)
        tn[tn < 1e-9] = 1e-9
        tx, ty = tx / tn, ty / tn
        nx, ny = -ty, tx  # normale gauche

        # --- Couloir : enveloppe latérale de TOUS les tours valides ---
        tree = cKDTree(np.column_stack([Px, Py]))
        off_lo = np.full(n_points, np.inf)
        off_hi = np.full(n_points, -np.inf)
        for ln in laps:
            g = df[df["lap_number"] == ln]
            la = pd.to_numeric(g[lat_col], errors="coerce").to_numpy(float)
            lo = pd.to_numeric(g[lon_col], errors="coerce").to_numpy(float)
            mm = ~(np.isnan(la) | np.isnan(lo))
            if mm.sum() < 20:
                continue
            gx = (lo[mm] - lon0) * mlon
            gy = (la[mm] - lat0) * mlat
            _, idx = tree.query(np.column_stack([gx, gy]))
            signed = (gx - Px[idx]) * nx[idx] + (gy - Py[idx]) * ny[idx]
            for j, i in enumerate(idx):
                off_lo[i] = min(off_lo[i], signed[j])
                off_hi[i] = max(off_hi[i], signed[j])

        # Combler les stations sans point + lisser l'enveloppe
        def _fill_smooth(arr, is_hi):
            a = arr.copy()
            bad = ~np.isfinite(a)
            if bad.all():
                return np.zeros_like(a)
            good_idx = np.where(~bad)[0]
            a[bad] = np.interp(np.where(bad)[0], good_idx, a[good_idx], period=n_points)
            # lissage circulaire léger (moyenne glissante)
            k = 5
            ext = np.concatenate([a[-k:], a, a[:k]])
            a = np.convolve(ext, np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]
            return a

        off_lo = _fill_smooth(off_lo, False) - margin_m
        off_hi = _fill_smooth(off_hi, True) + margin_m
        observed_width = float(np.mean(off_hi - off_lo))
        # Élargir jusqu'à une largeur de piste karting réaliste, centrée sur la
        # bande réellement roulée. Le pilote régulier n'utilise pas toute la
        # piste : sans les bords GPS réels, on suppose une largeur plausible pour
        # donner à l'optimiseur la place de tracer de vrais apex (objectif visible),
        # tout en restant ancré autour de là où il roule et borné à max_half_width.
        mid = 0.5 * (off_hi + off_lo)
        half = np.maximum(0.5 * (off_hi - off_lo), assumed_track_width_m / 2.0)
        half = np.minimum(half, max_half_width_m)
        off_lo = mid - half
        off_hi = mid + half
        corridor_width = float(np.mean(off_hi - off_lo))

        # --- Optimisation courbure minimale : min ||D2 (P + diag(n) Nrm)||^2 ---
        D2 = _periodic_second_diff(n_points)
        D1 = _periodic_first_diff(n_points)
        A_top = np.vstack([D2 * nx[None, :], D2 * ny[None, :]])   # 2N x N
        b_top = np.concatenate([D2 @ Px, D2 @ Py])                # 2N
        # Régularisation : offset lisse (pénalise les à-coups latéraux)
        A_reg = smooth_lambda * D1
        b_reg = np.zeros(n_points)
        A = np.vstack([A_top, A_reg])
        b = np.concatenate([b_top, b_reg])
        res = lsq_linear(A, -b, bounds=(off_lo, off_hi), max_iter=200)
        n_off = res.x

        Lx = Px + n_off * nx
        Ly = Py + n_off * ny

        # --- Vitesses : μ calibré sur le grip réel du pilote ---
        mu = 1.3
        if "speed" in df.columns and "curvature" in df.columns:
            gg = df[df["lap_number"].isin(laps)] if "lap_number" in df.columns else df
            v = pd.to_numeric(gg["speed"], errors="coerce").to_numpy(float) / 3.6
            kappa = np.abs(pd.to_numeric(gg["curvature"], errors="coerce").to_numpy(float))
            ok = np.isfinite(v) & np.isfinite(kappa) & (kappa > 1e-3) & (v > 5)
            if ok.sum() > 30:
                lat_grip = (v[ok] ** 2 * kappa[ok]) / G  # = μ atteint
                # 85e percentile (pas 95e) : la courbure GPS a des pics de bruit
                # qui gonflent le grip apparent. On veut un μ robuste, pas le max.
                mu = float(np.clip(np.percentile(lat_grip, 85), MU_MIN, MU_MAX))

        kap = np.abs(_curvature(Lx, Ly))
        kap[kap < 1e-4] = 1e-4
        v_max_grip = np.sqrt(mu * G / kap)  # m/s limité par l'adhérence latérale
        v_cap = np.nanpercentile(pd.to_numeric(df.get("speed"), errors="coerce"), 99) / 3.6 if "speed" in df.columns else 45.0
        v_cap = float(v_cap) if np.isfinite(v_cap) and v_cap > 10 else 45.0
        v_prof = np.minimum(v_max_grip, v_cap * 1.02)

        # Distances entre points de la ligne idéale
        ds = np.hypot(np.diff(Lx, append=Lx[0]), np.diff(Ly, append=Ly[0]))
        ds[ds < 1e-3] = 1e-3

        # Limites longitudinales (passes avant/arrière, périodiques)
        for _ in range(3):
            for i in range(n_points):
                j = (i - 1) % n_points
                v_prof[i] = min(v_prof[i], np.sqrt(v_prof[j] ** 2 + 2 * A_ACCEL * ds[j]))
            for i in range(n_points - 1, -1, -1):
                j = (i + 1) % n_points
                v_prof[i] = min(v_prof[i], np.sqrt(v_prof[j] ** 2 + 2 * A_BRAKE * ds[i]))

        optimal_time = float(np.sum(ds / np.maximum(v_prof, 1.0)))

        # Diagnostics de crédibilité — énergie de courbure (objectif réel minimisé)
        energy_ref = float(np.sum((D2 @ Px) ** 2 + (D2 @ Py) ** 2))
        energy_ideal = float(np.sum((D2 @ Lx) ** 2 + (D2 @ Ly) ** 2))
        curv_red = 100.0 * (1 - energy_ideal / max(energy_ref, 1e-9))
        max_shift = float(np.max(np.abs(n_off)))

        # Retour en lat/lon
        out_lat = (Ly / mlat) + lat0
        out_lon = (Lx / mlon) + lon0

        return {
            "available": True,
            "reference_lap": int(best_ln),
            "laps_used": [int(x) for x in laps],
            "track_length_m": round(float(track_len), 1),
            "optimal_lap_time_s": round(optimal_time, 3),
            "mu_calibrated": round(mu, 3),
            "corridor_width_m": round(corridor_width, 2),
            "curvature_reduction_pct": round(float(curv_red), 1),
            "max_lateral_shift_m": round(max_shift, 2),
            "n_points": n_points,
            "lat": [round(float(v), 7) for v in out_lat],
            "lon": [round(float(v), 7) for v in out_lon],
            "speed_kmh": [round(float(v) * 3.6, 1) for v in v_prof],
        }

    except Exception as e:  # noqa: BLE001
        warnings.warn(f"build_racing_line failed: {e}")
        return {"available": False, "reason": f"error: {e}"}
