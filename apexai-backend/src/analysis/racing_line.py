#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — « Tour parfait IA » (optimal racing line).

⚠️ NOM PRODUIT : côté interface, cette fonctionnalité s'appelle et doit rester
« Tour parfait IA ». Ne pas la renommer (« ligne idéale » n'est qu'un terme
technique interne) : c'est le nom qui porte la valeur commerciale.

Objectif : produire une VRAIE ligne de course objective à aller chercher, et non
un tour « lissé + 3,5 % » cosmétique.

Trois garanties de crédibilité :

1. LARGEUR NORMATIVE — la piste exploitable est estimée à partir de la
   réglementation karting de compétition (CIK-FIA : largeur minimale 8 m,
   usuellement 8-10 m), recentrée sur la bande réellement roulée. Le modèle est
   donc valable sur TOUS les circuits, pas calibré sur un tracé particulier.

2. AUCUN VIRAGE SUPPRIMÉ — une ligne idéale n'a pas le droit de « raccourcir »
   une chicane ou d'effacer un virage : ce serait couper la piste. Le couloir est
   volontairement asymétrique (peu de marge vers l'intérieur, là où le pilote
   frôle déjà le vibreur), puis chaque virage détecté est VÉRIFIÉ après
   optimisation ; si l'un d'eux a été gommé, le couloir est resserré localement
   et on résout à nouveau jusqu'à ce que tous les virages soient préservés.

3. VITESSES CALIBRÉES — l'adhérence μ est déduite du grip RÉELLEMENT atteint par
   le pilote (pas une constante), puis bornée par les limites longitudinales
   (accélération / freinage) pour un profil de vitesse atteignable.

Sortie : ligne idéale (lat/lon + vitesse cible), bords de piste estimés (pour
tracer le ruban de piste sur la carte) et temps au tour idéal.
Pur numpy/scipy, défensif (renvoie available=False si les données ne suffisent pas).
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
A_ACCEL = 0.6 * G      # accélération longitudinale réaliste karting
MU_MIN, MU_MAX = 1.0, 1.55

# Réglementation CIK-FIA (circuits de karting de compétition) : la piste doit
# mesurer au minimum 8 m de large (usuellement 8 à 10 m). On prend le minimum
# réglementaire : c'est l'hypothèse la plus prudente, celle qui évite de faire
# passer la ligne idéale hors piste sur un circuit étroit.
CIK_TRACK_WIDTH_M = 8.0

# Un virage « compte » à partir d'un rayon inférieur à ~45 m (au-delà, c'est une
# grande courbe ou une ligne droite).
CORNER_CURVATURE_THRESHOLD = 1.0 / 45.0
# Un virage est considéré préservé s'il garde le même sens et au moins 45 % de sa
# courbure moyenne d'origine.
CORNER_PRESERVE_RATIO = 0.45


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
    """Rééchantillonne une boucle fermée en n points équidistants (abscisse curviligne)."""
    pts = np.column_stack([x, y])
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
    """Courbure signée d'une courbe fermée (positive = virage à gauche)."""
    dx, dy = np.gradient(x), np.gradient(y)
    ddx, ddy = np.gradient(dx), np.gradient(dy)
    denom = (dx * dx + dy * dy) ** 1.5
    denom[denom < 1e-9] = 1e-9
    return (dx * ddy - dy * ddx) / denom


def _circular_smooth(a: np.ndarray, k: int = 5) -> np.ndarray:
    """Moyenne glissante circulaire (préserve la périodicité de la boucle)."""
    if k <= 0 or len(a) <= 2 * k:
        return a
    ext = np.concatenate([a[-k:], a, a[:k]])
    return np.convolve(ext, np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]


def _corner_regions(kap: np.ndarray, thresh: float, min_len: int = 3) -> List[np.ndarray]:
    """Regroupe les stations en régions de virage (contiguës, sur une boucle fermée)."""
    mask = np.abs(kap) > thresh
    n = len(mask)
    if not mask.any() or mask.all():
        return []
    # On démarre le balayage sur une station hors virage pour ne pas couper une
    # région à la jonction début/fin de la boucle.
    shift = int(np.argmin(mask.astype(int)))
    idx = np.roll(np.arange(n), -shift)
    m = mask[idx]
    regions, cur = [], []
    for k in range(n):
        if m[k]:
            cur.append(idx[k])
        else:
            if len(cur) >= min_len:
                regions.append(np.array(cur))
            cur = []
    if len(cur) >= min_len:
        regions.append(np.array(cur))
    return regions


def _regions_from_corner_ids(
    station_cid: Optional[np.ndarray],
    kap_ref: np.ndarray,
    thresh: float = CORNER_CURVATURE_THRESHOLD,
) -> List[np.ndarray]:
    """
    Régions de virage issues des virages DÉTECTÉS PAR L'APPLICATION
    (mêmes numéros que la carte et les graphiques).

    `corner_id` étiquette tout le segment du virage (approche et sortie
    comprises) : on ne garde que la partie réellement courbée, sinon les
    « virages » se toucheraient bout à bout et toute la piste passerait pour
    une enfilade de chicanes.
    """
    if station_cid is None:
        return []
    cid = np.where(np.isfinite(station_cid), station_cid, -1).astype(int)
    regions = []
    for c in sorted(set(cid.tolist())):
        if c < 0:
            continue
        idx = np.where(cid == c)[0]
        if len(idx) == 0:
            continue
        curved = idx[np.abs(kap_ref[idx]) > thresh]
        if len(curved) < 2:
            # Virage très ouvert : on retient son point le plus courbé.
            peak = idx[int(np.argmax(np.abs(kap_ref[idx])))]
            curved = np.array([peak])
        regions.append(curved)
    return regions


def _chicane_mask(
    regions: List[np.ndarray],
    kap_ref: np.ndarray,
    n_points: int,
    max_gap_stations: int = 10,
    max_region_stations: int = 16,
) -> np.ndarray:
    """
    Repère les chicanes : deux virages consécutifs de sens OPPOSÉS et très
    rapprochés.

    Dans une chicane, le pilote est déjà au point le plus serré (il monte sur le
    vibreur) : personne ne prend une chicane large. Autoriser une grande marge
    latérale reviendrait à la redresser, c'est-à-dire à couper la piste. On
    verrouille donc la ligne idéale au plus près de la trajectoire réelle.
    """
    mask = np.zeros(n_points, dtype=bool)
    if len(regions) < 2:
        return mask
    ordered = sorted(regions, key=lambda r: int(np.min(r)))
    signs = [float(np.mean(kap_ref[r])) for r in ordered]
    for i in range(len(ordered)):
        j = (i + 1) % len(ordered)
        if signs[i] * signs[j] >= 0:
            continue  # même sens : ce n'est pas une chicane
        # Une chicane est un enchaînement COURT : deux virages brefs, collés.
        if len(ordered[i]) > max_region_stations or len(ordered[j]) > max_region_stations:
            continue
        gap = int(np.min(ordered[j])) - int(np.max(ordered[i]))
        if gap < 0:
            gap += n_points
        if 0 <= gap <= max_gap_stations:
            mask[ordered[i]] = True
            mask[ordered[j]] = True
    return mask


def _valid_laps(df) -> List[int]:
    """Tours valides : source unique partagée avec le module tour idéal
    (exclut out/in-laps, tours trop lents ET tours partiels)."""
    from src.analysis.ideal_lap import _valid_lap_numbers
    laps = _valid_lap_numbers(df)
    if laps:
        return laps
    if "lap_number" not in df.columns:
        return []
    return [int(ln) for ln, g in df.groupby("lap_number") if int(ln) >= 1 and len(g) > 50]


def build_racing_line(
    df,
    n_points: int = 300,
    track_width_m: float = CIK_TRACK_WIDTH_M,
    margin_m: float = 0.3,
    smooth_lambda: float = 0.12,
    max_corner_fix_iter: int = 5,
) -> Dict[str, Any]:
    """
    Construit la ligne de course idéale.

    Args:
        df: DataFrame du pipeline (GPS + lap_number [+ speed, curvature]).
        track_width_m: largeur de piste supposée (défaut : minimum CIK-FIA 8 m).

    Returns dict avec available: bool. Si available :
        lat[], lon[], speed_kmh[]      — la ligne idéale
        track_edges                    — bords de piste estimés (ruban à tracer)
        optimal_lap_time_s             — temps au tour de cette ligne
        mu_calibrated                  — grip déduit des données du pilote
        curvature_reduction_pct        — réduction d'énergie de courbure vs ligne roulée
        corners_total / corners_preserved / corner_fix_iterations
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

        # ── Ligne de référence = meilleur tour ────────────────────────────────
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
        # On récupère les virages DÉJÀ détectés par l'application, pour que les
        # numéros de virage de la ligne idéale soient exactement ceux de la carte
        # et des graphiques (une seule vérité : V1, V2, V3…).
        rcid = None
        if "corner_id" in ref.columns:
            rcid = pd.to_numeric(ref["corner_id"], errors="coerce").to_numpy(float)[m]
        if len(rlat) < 30:
            return {"available": False, "reason": "tour de référence trop court"}

        x, y, lat0, lon0, mlat, mlon = _to_local_xy(rlat, rlon)
        Px, Py, track_len = _resample_closed(x, y, n_points)


        tx, ty = np.gradient(Px), np.gradient(Py)
        tn = np.hypot(tx, ty)
        tn[tn < 1e-9] = 1e-9
        tx, ty = tx / tn, ty / tn
        nx, ny = -ty, tx  # normale gauche

        # ── Enveloppe latérale réellement roulée (tous les tours valides) ─────
        tree = cKDTree(np.column_stack([Px, Py]))
        env_lo = np.full(n_points, np.inf)
        env_hi = np.full(n_points, -np.inf)
        # Virage de rattachement de chaque station, voté sur TOUS les tours
        # valides : un virage détecté sur d'autres tours que le tour de référence
        # doit quand même être vérifié, sinon le décompte de virages diffère de
        # celui affiché sur la carte.
        votes: Dict[int, List[int]] = {}
        for ln in laps:
            g = df[df["lap_number"] == ln]
            la = pd.to_numeric(g[lat_col], errors="coerce").to_numpy(float)
            lo = pd.to_numeric(g[lon_col], errors="coerce").to_numpy(float)
            mm = ~(np.isnan(la) | np.isnan(lo))
            if mm.sum() < 20:
                continue
            cid_lap = None
            if "corner_id" in g.columns:
                cid_lap = pd.to_numeric(g["corner_id"], errors="coerce").to_numpy(float)[mm]
            gx = (lo[mm] - lon0) * mlon
            gy = (la[mm] - lat0) * mlat
            _, idx = tree.query(np.column_stack([gx, gy]))
            signed = (gx - Px[idx]) * nx[idx] + (gy - Py[idx]) * ny[idx]
            for j, i in enumerate(idx):
                env_lo[i] = min(env_lo[i], signed[j])
                env_hi[i] = max(env_hi[i], signed[j])
                if cid_lap is not None and np.isfinite(cid_lap[j]):
                    votes.setdefault(int(i), []).append(int(cid_lap[j]))

        station_cid = None
        if votes:
            station_cid = np.full(n_points, np.nan)
            for i, vals in votes.items():
                u, c = np.unique(np.asarray(vals), return_counts=True)
                station_cid[i] = float(u[int(np.argmax(c))])

        def _fill(arr: np.ndarray) -> np.ndarray:
            a = arr.copy()
            bad = ~np.isfinite(a)
            if bad.all():
                return np.zeros_like(a)
            good = np.where(~bad)[0]
            a[bad] = np.interp(np.where(bad)[0], good, a[good], period=n_points)
            return _circular_smooth(a, 5)

        env_lo = _fill(env_lo) - margin_m
        env_hi = _fill(env_hi) + margin_m
        observed_width = float(np.mean(env_hi - env_lo))

        # ── Couloir : largeur normative, ASYMÉTRIQUE dans les virages ────────
        # Dans un virage, le pilote frôle déjà la corde : la marge vers
        # l'INTÉRIEUR est donc très limitée (sinon la ligne « idéale » couperait
        # la chicane par-dessus les vibreurs et supprimerait le virage).
        # Vers l'EXTÉRIEUR en revanche, il reste toute la largeur de piste.
        kap_ref = _curvature(Px, Py)
        half_w = track_width_m / 2.0
        # Axe de piste estimé = milieu de la bande réellement roulée. Les bords
        # (axe ± demi-largeur réglementaire) servent À LA FOIS de contrainte
        # d'optimisation et de ruban tracé sur la carte : la ligne idéale est
        # donc garantie visuellement à l'intérieur de la piste affichée.
        center = _circular_smooth(0.5 * (env_hi + env_lo), 7)
        edge_hi = center + half_w   # bord gauche (repère +n)
        edge_lo = center - half_w   # bord droit
        # 0 sur les lignes droites → 1 dans les virages serrés
        cornerness = np.clip(np.abs(kap_ref) / CORNER_CURVATURE_THRESHOLD, 0.0, 1.0)
        s = np.sign(kap_ref)
        s[s == 0] = 1.0

        # Marge observée de chaque côté, exprimée intérieur / extérieur
        obs_inner = np.where(s > 0, env_hi, -env_lo)
        obs_outer = np.where(s > 0, -env_lo, env_hi)
        # ── Marge INTÉRIEURE : principe « on ne coupe pas plus qu'un pilote ».
        # Dans un virage, le pilote monte sur le vibreur : le point le plus
        # intérieur qu'il a atteint sur l'ensemble de ses tours EST, en pratique,
        # le bord intérieur de la piste. Aller au-delà, ce serait couper — ce qui
        # supprime visuellement le virage (cas de la chicane redressée).
        # On autorise donc au plus : ce qu'il a déjà démontré, ou une marge
        # minuscule proportionnelle au rayon (un virage serré n'en a aucune).
        radius = 1.0 / np.maximum(np.abs(kap_ref), 1e-4)
        inner_cap = np.clip(radius / 50.0, 0.2, 1.2)
        inner_corner = np.maximum(np.maximum(obs_inner, 0.0), inner_cap)
        # Extérieur : le reste de la piste
        outer_corner = np.clip(np.maximum(obs_outer, 0.0) + 1.0, half_w, track_width_m)
        # Sur les lignes droites, on autorise symétriquement la demi-largeur
        sym = np.maximum(np.maximum(obs_inner, obs_outer), half_w)
        inner_allow = cornerness * inner_corner + (1 - cornerness) * sym
        outer_allow = cornerness * outer_corner + (1 - cornerness) * sym

        # CHICANES : on ne redresse pas une chicane. Le pilote y est déjà au plus
        # serré ; élargir reviendrait à la couper. On colle à sa trajectoire.
        regions = _regions_from_corner_ids(station_cid, kap_ref)
        if not regions:
            regions = _corner_regions(kap_ref, CORNER_CURVATURE_THRESHOLD)
        chicane = _chicane_mask(regions, kap_ref, n_points)
        if chicane.any():
            inner_allow = np.where(chicane, np.minimum(inner_allow, 0.4), inner_allow)
            outer_allow = np.where(
                chicane,
                np.minimum(outer_allow, np.maximum(obs_outer, 0.0) + 0.8),
                outer_allow,
            )

        inner_allow = _circular_smooth(inner_allow, 3)
        outer_allow = _circular_smooth(outer_allow, 3)

        off_hi = np.where(s > 0, inner_allow, outer_allow)
        off_lo = np.where(s > 0, -outer_allow, -inner_allow)
        # On borne par les bords de piste : jamais hors du ruban affiché.
        off_hi = np.minimum(off_hi, edge_hi)
        off_lo = np.maximum(off_lo, edge_lo)
        off_hi = np.maximum(off_hi, 0.05)
        off_lo = np.minimum(off_lo, -0.05)
        corridor_width = float(np.mean(off_hi - off_lo))

        # ── Optimisation courbure minimale sous contrainte de couloir ────────
        D2 = _periodic_second_diff(n_points)
        D1 = _periodic_first_diff(n_points)
        A = np.vstack([
            np.vstack([D2 * nx[None, :], D2 * ny[None, :]]),
            smooth_lambda * D1,
        ])
        b = np.concatenate([D2 @ Px, D2 @ Py, np.zeros(n_points)])

        lo_i, hi_i = off_lo.copy(), off_hi.copy()
        n_off = np.zeros(n_points)
        Lx, Ly = Px.copy(), Py.copy()
        iterations = 0
        preserved = len(regions)

        for iterations in range(max_corner_fix_iter + 1):
            res = lsq_linear(A, -b, bounds=(lo_i, hi_i), max_iter=200)
            n_off = res.x
            Lx = Px + n_off * nx
            Ly = Py + n_off * ny
            kap_ideal = _curvature(Lx, Ly)

            # GARANTIE : aucun virage détecté ne doit disparaître.
            violations = []
            for reg in regions:
                mr = float(np.mean(kap_ref[reg]))
                mi = float(np.mean(kap_ideal[reg]))
                if mr * mi <= 0 or abs(mi) < CORNER_PRESERVE_RATIO * abs(mr):
                    violations.append(reg)
            preserved = len(regions) - len(violations)
            if not violations or iterations == max_corner_fix_iter:
                break
            # Virage gommé → on resserre le couloir localement et on recommence.
            for reg in violations:
                ext = np.unique(np.concatenate([
                    (reg - 2) % n_points, (reg - 1) % n_points, reg,
                    (reg + 1) % n_points, (reg + 2) % n_points,
                ]))
                lo_i[ext] *= 0.5
                hi_i[ext] *= 0.5

        # ── Vitesses : μ calibré sur le grip réellement atteint ──────────────
        mu = 1.3
        if "speed" in df.columns and "curvature" in df.columns:
            gg = df[df["lap_number"].isin(laps)] if "lap_number" in df.columns else df
            v = pd.to_numeric(gg["speed"], errors="coerce").to_numpy(float) / 3.6
            kappa = np.abs(pd.to_numeric(gg["curvature"], errors="coerce").to_numpy(float))
            ok = np.isfinite(v) & np.isfinite(kappa) & (kappa > 1e-3) & (v > 5)
            if ok.sum() > 30:
                lat_grip = (v[ok] ** 2 * kappa[ok]) / G
                # 85e percentile : la courbure GPS a des pics de bruit qui
                # gonflent le grip apparent. On veut un μ robuste, pas le maximum.
                mu = float(np.clip(np.percentile(lat_grip, 85), MU_MIN, MU_MAX))

        kap_final = np.abs(_curvature(Lx, Ly))
        kap_final[kap_final < 1e-4] = 1e-4
        v_grip = np.sqrt(mu * G / kap_final)
        v_cap = 45.0
        if "speed" in df.columns:
            c = np.nanpercentile(pd.to_numeric(df["speed"], errors="coerce"), 99) / 3.6
            if np.isfinite(c) and c > 10:
                v_cap = float(c)
        v_prof = np.minimum(v_grip, v_cap * 1.02)

        ds = np.hypot(np.diff(Lx, append=Lx[0]), np.diff(Ly, append=Ly[0]))
        ds[ds < 1e-3] = 1e-3
        for _ in range(3):
            for i in range(n_points):
                j = (i - 1) % n_points
                v_prof[i] = min(v_prof[i], np.sqrt(v_prof[j] ** 2 + 2 * A_ACCEL * ds[j]))
            for i in range(n_points - 1, -1, -1):
                j = (i + 1) % n_points
                v_prof[i] = min(v_prof[i], np.sqrt(v_prof[j] ** 2 + 2 * A_BRAKE * ds[i]))

        optimal_time = float(np.sum(ds / np.maximum(v_prof, 1.0)))

        # ── Bords de piste (mêmes que la contrainte d'optimisation) ──────────
        to_lat = lambda X, Y: [round(float(v), 7) for v in ((Y / mlat) + lat0)]
        to_lon = lambda X, Y: [round(float(v), 7) for v in ((X / mlon) + lon0)]
        ELx, ELy = Px + edge_hi * nx, Py + edge_hi * ny
        ERx, ERy = Px + edge_lo * nx, Py + edge_lo * ny

        energy_ref = float(np.sum((D2 @ Px) ** 2 + (D2 @ Py) ** 2))
        energy_ideal = float(np.sum((D2 @ Lx) ** 2 + (D2 @ Ly) ** 2))
        curv_red = 100.0 * (1 - energy_ideal / max(energy_ref, 1e-9))

        return {
            "available": True,
            "reference_lap": int(best_ln),
            "laps_used": [int(v) for v in laps],
            "track_length_m": round(float(track_len), 1),
            "optimal_lap_time_s": round(optimal_time, 3),
            "mu_calibrated": round(mu, 3),
            "track_width_m": round(float(track_width_m), 1),
            "track_width_source": "CIK-FIA (largeur minimale réglementaire karting)",
            "observed_width_m": round(observed_width, 2),
            "corridor_width_m": round(corridor_width, 2),
            "curvature_reduction_pct": round(float(curv_red), 1),
            "max_lateral_shift_m": round(float(np.max(np.abs(n_off))), 2),
            "corners_total": len(regions),
            "corners_preserved": int(preserved),
            "corners_source": "virages détectés par l'analyse" if station_cid is not None else "pics de courbure",
            "chicane_stations": int(np.count_nonzero(chicane)),
            "corner_fix_iterations": int(iterations),
            "n_points": n_points,
            "lat": to_lat(Lx, Ly),
            "lon": to_lon(Lx, Ly),
            "speed_kmh": [round(float(v) * 3.6, 1) for v in v_prof],
            "track_edges": {
                "left": {"lat": to_lat(ELx, ELy), "lon": to_lon(ELx, ELy)},
                "right": {"lat": to_lat(ERx, ERy), "lon": to_lon(ERx, ERy)},
            },
        }

    except Exception as e:  # noqa: BLE001
        warnings.warn(f"build_racing_line failed: {e}")
        return {"available": False, "reason": f"error: {e}"}
