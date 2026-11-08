"""
Accélérateur et frein quand le boîtier n'a pas de capteur de pédale.

Un MyChron ou un Alfano sans extension n'enregistre pas la position des
pédales : Race Studio ne montre alors pas de « % d'accélérateur » mais le
régime moteur (RPM) et l'accélération longitudinale (« GPS LonAcc »), et c'est
sur ces deux courbes que les pilotes lisent gaz et frein. On fait la même
lecture, chiffrée :

- accélération longitudinale : la voie « GPS LonAcc » du boîtier quand elle
  existe, sinon la dérivée de la vitesse ; si le régime suit la vitesse (kart
  en prise directe), la dérivée du régime, plus fine, la complète ;
- **gaz** : 100 % quand le kart accélère autant qu'il le peut à cette vitesse
  (enveloppe mesurée sur la séance, la même sortie d'épingle à fond donne
  100 %), 0 % quand il ne fait que ralentir de sa traînée (pied levé) ;
- **frein** : la décélération au-delà de la traînée, rapportée au freinage le
  plus fort de la séance.

Ce sont des estimations, signalées comme telles ; une vraie voie de capteur
(TPS, pression de frein) est toujours préférée.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

G = 9.81
# Traînée d'un kart pied levé : roulement + aérodynamique (CdA ~0,6 m², ~165 kg
# pilote compris). Sert de « zéro » entre gaz et frein.
ROLLING_G = 0.02
AERO_K = 0.5 * 1.2 * 0.6 / (165.0 * G)  # g par (m/s)²

THROTTLE_NAMES = ("throttle", "tps", "throttle pos", "throttle position", "gaz", "accelerateur", "pedal pos")
BRAKE_NAMES = ("brake press", "brake pressure", "brake pos", "brake", "frein", "pression frein")


def _find(df: pd.DataFrame, names) -> Optional[str]:
    cols = {c.lower().strip(): c for c in df.columns}
    for n in names:
        if n in cols:
            return cols[n]
    for c_low, c in cols.items():
        if any(c_low.startswith(n) for n in names):
            return c
    return None


def _to_pct(x: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(x.astype(float))
    lo, hi = np.nanpercentile(x, 1), np.nanpercentile(x, 99.5)
    if hi - lo < 1e-6:
        return np.zeros_like(x)
    return np.clip((x - lo) / (hi - lo) * 100.0, 0, 100)


def sensor_pedals(df: pd.DataFrame) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Voies réelles de capteurs (TPS, pression de frein), en 0-100, si le fichier les a."""
    t_col = _find(df, THROTTLE_NAMES)
    b_col = _find(df, BRAKE_NAMES)
    thr = _to_pct(pd.to_numeric(df[t_col], errors="coerce").to_numpy()) if t_col else None
    brk = _to_pct(pd.to_numeric(df[b_col], errors="coerce").to_numpy()) if b_col else None
    return thr, brk


def _smooth(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1:
        return x
    return pd.Series(x).rolling(n, center=True, min_periods=1).mean().to_numpy()


def longitudinal_g(df: pd.DataFrame, speed_kmh: np.ndarray, time_s: np.ndarray) -> np.ndarray:
    """Accélération longitudinale (g), la plus propre disponible."""
    n = len(speed_kmh)
    dt = np.nanmedian(np.diff(time_s)) if n > 2 else 0.05
    fs = 1.0 / dt if dt and dt > 0 else 20.0
    win = max(3, int(round(0.25 * fs)))  # ~0,25 s : le bruit GPS sans gommer un freinage

    v = np.nan_to_num(speed_kmh.astype(float)) / 3.6
    t = np.nan_to_num(time_s.astype(float))
    if np.all(np.diff(t) > 0):
        a_speed = np.gradient(_smooth(v, win), t) / G
    else:
        a_speed = np.gradient(_smooth(v, win)) * fs / G

    a = a_speed
    lon_col = _find(df, ("gps lonacc", "gps_lonacc", "longitudinal_g", "lon_g", "accel_lon", "inlineacc"))
    if lon_col:
        lon = pd.to_numeric(df[lon_col], errors="coerce").to_numpy(float)
        if np.isfinite(lon).mean() > 0.9 and np.nanstd(lon) > 0.05:
            a = _smooth(np.where(np.isfinite(lon), lon, a_speed), win)

    # Régime moteur : en prise directe (régime proportionnel à la vitesse), sa
    # dérivée est plus fine que celle du GPS et prouve l'action sur les gaz.
    rpm_col = _find(df, ("rpm", "engine rpm", "regime"))
    if rpm_col:
        rpm = pd.to_numeric(df[rpm_col], errors="coerce").to_numpy(float)
        ok = np.isfinite(rpm) & (rpm > 2000) & (v > 5)
        if ok.mean() > 0.6:
            ratio = v[ok] / rpm[ok]
            spread = np.nanstd(ratio) / max(np.nanmean(ratio), 1e-9)
            if spread < 0.08:  # une seule démultiplication : pas de boîte
                k = float(np.nanmedian(ratio))
                rpm_s = _smooth(np.where(np.isfinite(rpm), rpm, 0.0), win)
                a_rpm = (np.gradient(rpm_s, t) if np.all(np.diff(t) > 0) else np.gradient(rpm_s) * fs) * k / G
                a = np.where(ok, 0.5 * a + 0.5 * a_rpm, a)
    return np.nan_to_num(a)


def _lateral_g(df: pd.DataFrame, n: int) -> np.ndarray:
    col = _find(df, ("gps latacc", "lateral_g", "lat_g", "latacc"))
    if not col:
        return np.zeros(n)
    x = np.abs(pd.to_numeric(df[col], errors="coerce").to_numpy(float))
    return np.nan_to_num(x)


def estimate_pedals(df: pd.DataFrame, speed_kmh: np.ndarray, time_s: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Gaz et frein estimés (0-100) à partir de l'accélération longitudinale."""
    n = len(speed_kmh)
    if n < 10:
        return np.zeros(n), np.zeros(n)
    a = longitudinal_g(df, speed_kmh, time_s)
    v = np.nan_to_num(speed_kmh.astype(float)) / 3.6
    drag = ROLLING_G + AERO_K * v ** 2  # décélération pied levé (g)

    # Enveloppe « pleins gaz » : la meilleure accélération obtenue à chaque
    # vitesse ET à chaque charge latérale. En courbe rapide, pneus en appui,
    # un kart à fond accélère moins qu'en ligne droite : sans cette nuance,
    # une courbe prise à fond se lirait « gaz à moitié ».
    kmh = v * 3.6
    lat = _smooth(_lateral_g(df, n), 5)
    lat_edges = [0.0, 0.5, 1.0, 1.5, 9.0]
    on = a > -drag
    full = np.full(n, np.nan)
    sp_edges = np.arange(0, max(kmh.max(), 10) + 10, 10)

    def envelope(mask_lat):
        cs, es = [], []
        for lo in sp_edges[:-1]:
            m = mask_lat & on & (kmh >= lo) & (kmh < lo + 10)
            if m.sum() >= 15:
                cs.append(lo + 5)
                es.append(np.percentile(a[m], 90))
        if len(cs) < 2:
            return None
        es = np.maximum.accumulate(np.array(es)[::-1])[::-1]
        return np.array(cs), es

    base = envelope(np.ones(n, bool))
    for lo, hi in zip(lat_edges[:-1], lat_edges[1:]):
        sel = (lat >= lo) & (lat < hi)
        env = envelope(sel) or base
        if env is not None and sel.any():
            full[sel] = np.interp(kmh[sel], env[0], env[1])
    if base is not None:
        full = np.where(np.isfinite(full), full, np.interp(kmh, base[0], base[1]))
    else:
        full = np.where(np.isfinite(full), full, max(np.percentile(a, 95), 0.1))
    full = np.maximum(full, 0.0)

    thr = np.clip((a + drag) / np.maximum(full + drag, 0.05), 0, 1) * 100.0

    # Même règle que les phases de pilotage (braking.py) : près de la vitesse
    # de pointe, un kart qui ne perd pas de vitesse est pied au plancher — la
    # traînée y mange presque toute la puissance, l'accélération ne le montre plus.
    top = np.nanpercentile(kmh, 99.5) if n else 0.0
    thr = np.where((kmh >= 0.90 * top) & (a >= -0.03), 100.0, thr)

    decel = -a - drag
    brake_max = max(np.percentile(-a, 99), 0.3) - np.median(drag)
    brk = np.clip(decel / max(brake_max, 0.2), 0, 1) * 100.0
    # Petite marge sous la traînée : un pied levé n'est pas un freinage.
    brk[decel < 0.08] = 0.0
    thr[brk > 0] = 0.0
    return np.round(thr, 1), np.round(brk, 1)
