"""Accélérateur / frein sans capteur : lecture de l'accélération, comme Race Studio."""

import numpy as np
import pandas as pd

from src.analysis.pedals import AERO_K, ROLLING_G, estimate_pedals, sensor_pedals


def _lap(n_laps=6, fs=20):
    """Ligne droite à fond, gros freinage, épingle, remise des gaz à fond."""
    v, t, now = [], [], 0.0
    for _ in range(n_laps):
        speed = 55.0
        # accélération pleins gaz : a(v) décroît avec la vitesse (puissance)
        while speed < 115:
            ms = speed / 3.6
            a_full = 0.55 * (1 - speed / 125) - ROLLING_G - AERO_K * ms**2 + 0.25 * (1 - speed / 125)
            speed += max(a_full, 0.01) * 9.81 * 3.6 / fs
            v.append(speed); t.append(now); now += 1 / fs
        for _ in range(int(2.0 * fs)):  # freinage fort
            speed -= 1.0 * 9.81 * 3.6 / fs
            v.append(max(speed, 55)); t.append(now); now += 1 / fs
            speed = max(speed, 55)
    return pd.DataFrame({"speed": v, "time": t}), np.array(v), np.array(t)


def test_full_throttle_reads_full_and_braking_reads_brake():
    df, v, t = _lap()
    thr, brk = estimate_pedals(df, v, t)
    accel = np.r_[0, np.diff(v)] > 0
    decel = np.r_[0, np.diff(v)] < -0.5
    # sortie d'épingle et ligne droite à fond : la plupart des points à 90 % et plus
    assert np.mean(thr[accel][40:] >= 90) > 0.7
    assert np.median(brk[decel]) > 70
    assert np.all((thr == 0) | (brk == 0))  # jamais gaz et frein ensemble


def test_real_sensor_channels_win():
    df = pd.DataFrame({"TPS": [0, 50, 100, 100], "Brake Press": [0, 0, 10, 40]})
    thr, brk = sensor_pedals(df)
    assert thr is not None and brk is not None and thr.max() == 100
