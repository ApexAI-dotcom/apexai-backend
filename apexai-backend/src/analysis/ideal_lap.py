#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Tour idéal théorique & temps réellement perdu.

Idée : sur une session multi-tours, le pilote a rarement enchaîné son meilleur
passage sur CHAQUE portion dans le même tour. En découpant la piste en
mini-secteurs et en prenant, secteur par secteur, le meilleur temps réalisé sur
l'ensemble des tours valides, on reconstitue un « tour idéal » — un chrono
réellement atteignable par ce pilote, sur ce kart, ce jour-là.

Contrairement au `time_lost` historique (approximation à partir de la seule
vitesse apex), le temps perdu est ici mesuré sur les VRAIS temps du pilote :
pour chaque secteur, écart entre le temps du meilleur tour et le temps idéal.
Ce sont des secondes crédibles, pas une estimation physique.

La fonction est pure (pas d'I/O) et défensive : elle renvoie toujours un dict
avec `available` indiquant si le calcul a pu être fait (≥ 2 tours valides).
"""

from typing import Any, Dict, List, Optional
import warnings

import numpy as np
import pandas as pd


def _valid_lap_numbers(df: pd.DataFrame) -> List[int]:
    """
    Tours exploitables pour le tour idéal : on exclut le tour 0 (out/in-lap) et
    les tours nettement plus lents que la médiane (rentrée stand, trafic, drapeau).
    Même esprit que la détection d'outliers de `get_laps`.
    """
    if "lap_number" not in df.columns or "time" not in df.columns:
        return []
    times: Dict[int, float] = {}
    lengths: Dict[int, float] = {}
    for lap_num, g in df.groupby("lap_number", sort=True):
        lap_num = int(lap_num)
        if lap_num < 1:
            continue
        t = pd.to_numeric(g["time"], errors="coerce").dropna()
        if len(t) >= 2:
            times[lap_num] = float(t.max() - t.min())
        if "cumulative_distance" in g.columns:
            d = pd.to_numeric(g["cumulative_distance"], errors="coerce").dropna()
            if len(d) >= 2:
                lengths[lap_num] = float(d.max() - d.min())
    good = [ln for ln, tv in times.items() if tv > 0]
    if len(good) < 2:
        return good
    median_time = float(np.median([times[ln] for ln in good]))
    median_len = float(np.median([lengths[ln] for ln in good if ln in lengths])) if lengths else None
    valid = []
    for ln in good:
        # Trop lent → tour de rentrée / trafic
        if times[ln] > 1.15 * median_time:
            continue
        # Longueur incohérente → tour partiel (beacon manqué)
        if median_len and ln in lengths and not (0.8 * median_len <= lengths[ln] <= 1.2 * median_len):
            continue
        valid.append(ln)
    return valid


def compute_ideal_lap(
    df: pd.DataFrame,
    sector_length_m: float = 25.0,
    min_sectors: int = 8,
    max_sectors: int = 200,
) -> Dict[str, Any]:
    """
    Calcule le tour idéal théorique et le temps réel perdu par secteur/virage.

    Args:
        df: DataFrame du pipeline (colonnes lap_number, time, cumulative_distance ;
            corner_id optionnel pour l'attribution par virage).
        sector_length_m: longueur cible d'un mini-secteur (mètres).

    Returns:
        dict avec au minimum {available: bool}. Si available:
          - best_real_lap_time_s, best_lap_number
          - ideal_lap_time_s
          - potential_gain_s        (best_real - ideal, ≥ 0)
          - laps_used               (liste des lap_number retenus)
          - sectors: [{index, start_m, end_m, ideal_time_s, best_lap_time_s,
                       loss_s, from_lap, corner_id}]
          - per_corner_loss_s: {corner_id: secondes perdues sur le meilleur tour}
    """
    try:
        needed = {"lap_number", "time", "cumulative_distance"}
        if not needed.issubset(df.columns):
            return {"available": False, "reason": "colonnes manquantes (multi-tours requis)"}

        laps = _valid_lap_numbers(df)
        if len(laps) < 2:
            return {"available": False, "reason": "moins de 2 tours valides", "laps_used": laps}

        # Profils temps(distance) normalisés par tour (distance et temps repartent de 0).
        lap_profiles: Dict[int, Dict[str, np.ndarray]] = {}
        lap_times: Dict[int, float] = {}
        lengths = []
        for ln in laps:
            g = df[df["lap_number"] == ln]
            d = pd.to_numeric(g["cumulative_distance"], errors="coerce").to_numpy(dtype=float)
            t = pd.to_numeric(g["time"], errors="coerce").to_numpy(dtype=float)
            mask = ~(np.isnan(d) | np.isnan(t))
            d, t = d[mask], t[mask]
            if len(d) < 3:
                continue
            order = np.argsort(d)
            d, t = d[order], t[order]
            d = d - d[0]
            t = t - t[0]
            # Distance strictement croissante pour np.interp
            keep = np.concatenate(([True], np.diff(d) > 1e-6))
            d, t = d[keep], t[keep]
            if len(d) < 3:
                continue
            corner = None
            if "corner_id" in g.columns:
                corner = pd.to_numeric(g["corner_id"], errors="coerce").to_numpy(dtype=float)
                corner = corner[mask][order][keep]
            lap_profiles[ln] = {"dist": d, "time": t, "corner": corner}
            lap_times[ln] = float(t[-1])
            lengths.append(float(d[-1]))

        if len(lap_profiles) < 2:
            return {"available": False, "reason": "profils insuffisants"}

        track_len = float(np.median(lengths))
        n_sectors = int(round(track_len / max(1.0, sector_length_m)))
        n_sectors = max(min_sectors, min(max_sectors, n_sectors))
        edges = np.linspace(0.0, track_len, n_sectors + 1)

        # Temps cumulé de chaque tour aux frontières de secteurs.
        cum_by_lap: Dict[int, np.ndarray] = {}
        for ln, prof in lap_profiles.items():
            cum_by_lap[ln] = np.interp(edges, prof["dist"], prof["time"])

        best_real_lap = min(lap_times, key=lambda k: lap_times[k])
        best_real_time = lap_times[best_real_lap]

        # Corner dominant par secteur, lu sur le meilleur tour (repère lisible).
        best_prof = lap_profiles[best_real_lap]

        def corner_for_sector(i: int) -> Optional[int]:
            if best_prof["corner"] is None:
                return None
            lo, hi = edges[i], edges[i + 1]
            m = (best_prof["dist"] >= lo) & (best_prof["dist"] < hi)
            vals = best_prof["corner"][m]
            vals = vals[~np.isnan(vals)]
            if len(vals) == 0:
                return None
            # Mode (corner le plus présent dans le secteur)
            uniq, counts = np.unique(vals.astype(int), return_counts=True)
            return int(uniq[np.argmax(counts)])

        # Virage de rattachement de CHAQUE secteur. Une portion de ligne droite
        # n'a pas de virage propre : le temps qu'on y perd vient de la sortie du
        # virage précédent (vitesse emportée). On la rattache donc à ce virage —
        # c'est la lecture d'un ingénieur, et surtout cela évite d'afficher une
        # « perte en ligne droite » orpheline que les conseils ignoreraient.
        raw_cids = [corner_for_sector(i) for i in range(n_sectors)]
        attributed: List[Optional[int]] = list(raw_cids)
        last_seen: Optional[int] = None
        for i in range(n_sectors):
            if raw_cids[i] is not None:
                last_seen = raw_cids[i]
        for i in range(n_sectors):
            if raw_cids[i] is not None:
                last_seen = raw_cids[i]
            attributed[i] = raw_cids[i] if raw_cids[i] is not None else last_seen

        sectors = []
        ideal_time = 0.0
        per_corner_loss: Dict[int, float] = {}
        # Temps passé dans chaque virage, TOUR PAR TOUR : permet de dire au
        # pilote *quand* il a perdu (« ton meilleur passage : tour 3 ») au lieu
        # d'un conseil hors sol qui ne renvoie à aucun tour précis.
        corner_lap_times: Dict[int, Dict[int, float]] = {}
        for i in range(n_sectors):
            sector_times = {ln: cum_by_lap[ln][i + 1] - cum_by_lap[ln][i] for ln in lap_profiles}
            from_lap = min(sector_times, key=lambda k: sector_times[k])
            ideal_st = float(sector_times[from_lap])
            best_st = float(sector_times[best_real_lap])
            loss = max(0.0, best_st - ideal_st)
            ideal_time += ideal_st
            cid = attributed[i]
            is_corner = raw_cids[i] is not None
            if cid is not None:
                if loss > 0:
                    per_corner_loss[cid] = per_corner_loss.get(cid, 0.0) + loss
                slot = corner_lap_times.setdefault(cid, {})
                for ln, st in sector_times.items():
                    slot[ln] = slot.get(ln, 0.0) + float(st)
            sectors.append({
                "index": i,
                "start_m": round(float(edges[i]), 1),
                "end_m": round(float(edges[i + 1]), 1),
                "ideal_time_s": round(ideal_st, 3),
                "best_lap_time_s": round(best_st, 3),
                "loss_s": round(loss, 3),
                "from_lap": int(from_lap),
                "corner_id": cid,
                # `in_corner` distingue la partie courbée de la relance qui suit :
                # la carte n'étiquette que les virages, pas les lignes droites.
                "in_corner": bool(is_corner),
            })

        potential_gain = max(0.0, best_real_time - ideal_time)

        # Synthèse par virage : meilleur tour, tour le plus coûteux, et
        # régularité (un défaut qui revient à chaque tour ne se corrige pas comme
        # une erreur isolée sur un seul tour).
        per_corner_laps: Dict[int, Dict[str, Any]] = {}
        for cid, by_lap in corner_lap_times.items():
            if len(by_lap) < 2:
                continue
            best_ln_c = min(by_lap, key=lambda k: by_lap[k])
            worst_ln_c = max(by_lap, key=lambda k: by_lap[k])
            ref = by_lap[best_ln_c]
            spread = by_lap[worst_ln_c] - ref
            losses = {int(ln): round(t - ref, 3) for ln, t in by_lap.items()}
            n_costly = sum(1 for v in losses.values() if v > 0.03)
            per_corner_laps[int(cid)] = {
                "best_lap": int(best_ln_c),
                "worst_lap": int(worst_ln_c),
                "spread_s": round(float(spread), 3),
                "loss_by_lap": losses,
                # « récurrent » = le pilote perd sur la majorité de ses tours
                "recurring": bool(n_costly >= max(2, (len(losses) - 1))),
            }

        return {
            "available": True,
            "laps_used": [int(x) for x in lap_profiles.keys()],
            "track_length_m": round(track_len, 1),
            "n_sectors": n_sectors,
            "best_lap_number": int(best_real_lap),
            "best_real_lap_time_s": round(best_real_time, 3),
            "ideal_lap_time_s": round(ideal_time, 3),
            "potential_gain_s": round(potential_gain, 3),
            "per_corner_loss_s": {int(k): round(v, 3) for k, v in per_corner_loss.items()},
            "per_corner_laps": per_corner_laps,
            "sectors": sectors,
        }

    except Exception as e:  # noqa: BLE001 — on ne casse jamais l'analyse pour le tour idéal
        warnings.warn(f"compute_ideal_lap failed: {e}")
        return {"available": False, "reason": f"error: {e}"}
