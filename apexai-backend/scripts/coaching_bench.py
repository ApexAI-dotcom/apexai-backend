#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Banc d'essai du coaching : rejoue l'analyse complète sur un dossier de
fichiers de séance (.csv AiM/MoTeC, .xrk/.xrz) et écrit, pour chaque séance
et chaque niveau, les conseils produits dans un JSON.

    python scripts/coaching_bench.py <dossier> <sortie.json> [--tiers visitor,rookie,racer]

La météo est désactivée (pas de réseau) : état de piste « sec » sauf si le
fichier dit autre chose. Sert à comparer l'avant / après d'un changement du
moteur de conseils sur de vraies séances.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")
os.environ.setdefault("APEX_WEATHER_OFFLINE", "1")

from src.core.session_header import read_session_header  # noqa: E402
from src.core.xrk_loader import is_xrk_filename, xrk_to_motec_csv  # noqa: E402
from src.api import services  # noqa: E402

DEMO_KART = {
    # Profil Racer type (celui d'Adria dans Mon Kart) pour tester le niveau
    # Racer sans compte : moteur, pneus, poids, châssis, pressions.
    "engine_model": "Rotax Max DD2",
    "tires_model": "Vega Blanc XM3",
    "driver_weight_kg": 73.0,
    "chassis_brand": "Sodi",
    "chassis_model": "Sigma RS3",
    "setup": {"cold_pressure_front": 0.60, "cold_pressure_rear": 0.62,
              "sprocket_front": 12, "sprocket_rear": 80,
              "track_width_rear": 1400, "track_width_front": 120},
}


def run(path: Path, tier: str | None):
    p = str(path)
    if is_xrk_filename(path.name):
        csv_path = Path(os.environ.get("TMPDIR", "/tmp")) / (path.stem + ".csv")
        csv_path.write_bytes(xrk_to_motec_csv(path.read_bytes()))
        p = str(csv_path)
    header = read_session_header(p)
    kwargs = dict(track_condition="dry", track_temperature=20.0,
                  circuit_name=header.get("circuit_name"))
    sig = inspect.signature(services._run_analysis_pipeline_sync).parameters
    if tier is not None and "coaching_tier" in sig:
        kwargs["coaching_tier"] = tier
        if tier in ("racer", "team") and "kart_context" in sig:
            kwargs["kart_context"] = DEMO_KART
        if "vehicle_hint" in sig:
            kwargs["vehicle_hint"] = header.get("vehicle")
    t0 = time.time()
    res = services._run_analysis_pipeline_sync(p, header["beacon_markers"], path.stem, datetime.now(), **kwargs)
    return res, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("out")
    ap.add_argument("--tiers", default="")
    a = ap.parse_args()
    tiers = [t for t in a.tiers.split(",") if t] or [None]
    out = {}
    for f in sorted(Path(a.folder).iterdir()):
        if f.suffix.lower() not in (".csv", ".xrk", ".xrz"):
            continue
        for tier in tiers:
            key = f"{f.name}|{tier or 'actuel'}"
            try:
                res, dt = run(f, tier)
                sc = res.get("session_conditions") or {}
                out[key] = {
                    "file": f.name, "tier": tier, "seconds": round(dt, 1),
                    "circuit": sc.get("circuit_name"),
                    "best_lap": res.get("best_lap_time"),
                    "laps": len(res.get("lap_times") or []),
                    "corners": res.get("corners_detected"),
                    "advice": res.get("coaching_advice"),
                    "coaching_meta": res.get("coaching"),
                }
                n = len([x for x in res.get("coaching_advice") or [] if x.get("category") != "info"])
                print(f"OK  {key:60s} {dt:5.1f}s  {n} conseils  {sc.get('circuit_name')}")
            except Exception as e:  # noqa: BLE001
                out[key] = {"file": f.name, "tier": tier, "error": str(e)}
                print(f"ERR {key}: {e}")
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
