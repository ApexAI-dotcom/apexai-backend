#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Banc d'essai sur de vraies séances : import, analyse complète, coaching par
niveau et comparaison des séances d'un même pilote le même jour.

    python scripts/coaching_bench.py <dossier> [<dossier> …] --out bench.json
        [--tiers visitor,rookie,racer] [--dump dossier_json] [--no-compare]

- Parcourt les dossiers récursivement : .csv (AiM / MoTeC / export Excel
  Alfano), .xrk / .xrz (AiM), .zip (Alfano ADA). Les annexes Race Studio
  (.drk, .rrk) doivent être refusées avec un message clair : c'est vérifié.
- Chaque fichier passe par la même conversion que l'API (normalize_upload),
  puis par le pipeline complet, pour chaque niveau demandé.
- Un même dossier de séance exporté sous plusieurs formats (aim.csv, .xrk,
  .xrz) doit donner le même meilleur tour et le même nombre de virages.
- Comparaison : pour chaque pilote et chaque jour, la séance 1 en analyse
  complète, la suivante en analyse allégée (comme le comparateur de l'app).
  Avec --dump, les deux résultats sont écrits en JSON pour le test du
  comparateur côté app (src/lib/compare.bench.test.ts, APEX_BENCH_DIR).

Les fichiers des pilotes restent HORS du dépôt : on passe leur dossier.
La météo est désactivée (pas de réseau) : piste sèche, 20 °C.
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import re
import sys
import tempfile
import time
import warnings
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
os.environ.setdefault("APEX_WEATHER_OFFLINE", "1")

from src.core.session_header import read_session_header  # noqa: E402
from src.core.xrk_loader import normalize_upload  # noqa: E402
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

SESSION_EXT = {".csv", ".xrk", ".xrz", ".zip"}
ANNEX_EXT = {".drk", ".rrk"}
TMP = Path(tempfile.mkdtemp(prefix="apex_bench_"))


# ───────────────────────────────────────────────────────────── import

def convert(path: Path) -> Path:
    """Même conversion que l'API (xrk/xrz/zip/Excel Alfano → CSV MoTeC)."""
    content, name = asyncio.run(normalize_upload(path.read_bytes(), path.name))
    out = TMP / f"{abs(hash(str(path)))}_{name}"
    out.write_bytes(content)
    return out


def device_of(csv_path: Path, original: Path) -> str:
    labels: Dict[str, str] = {}
    with open(csv_path, encoding="utf-8", errors="ignore") as f:
        for _, line in zip(range(20), f):
            parts = [p.strip().strip('"') for p in line.split('","')]
            if len(parts) >= 2:
                labels.setdefault(parts[0].strip('"').lower(), parts[1].strip('"'))
    dev = labels.get("device")
    if dev:
        return dev
    m = re.search(r"\d{4}-\d{2}-\d{2}-([a-z0-9]+)-", str(original.parent.name), re.I)
    model = {"mychron5": "AiM MyChron 5", "mychron5s": "AiM MyChron 5S", "solo2dl": "AiM Solo 2 DL"}.get((m.group(1) if m else "").lower())
    return f"{model or 'AiM'} (export Race Studio)"


def session_key(path: Path) -> str:
    """Identifiant de la séance : le dossier « date-boîtier-…-pilote-session-NN », sinon le fichier."""
    if re.match(r"\d{4}-\d{2}-\d{2}-.*-session-\d+$", path.parent.name):
        return path.parent.name
    return path.stem


def pilot_day(key: str) -> Optional[str]:
    m = re.match(r"(\d{4}-\d{2}-\d{2})-.*-([^-]+)-session-\d+$", key)
    return f"{m.group(1)}|{m.group(2).lower()}" if m else None


# ───────────────────────────────────────────────────────────── analyse

def analyse(csv_path: Path, tier: Optional[str], light: bool = False):
    header = read_session_header(str(csv_path))
    kwargs: Dict[str, Any] = dict(track_condition="dry", track_temperature=20.0,
                                  circuit_name=header.get("circuit_name"))
    sig = inspect.signature(services._run_analysis_pipeline_sync).parameters
    if light and "light" in sig:
        kwargs["light"] = True
    if tier is not None and "coaching_tier" in sig:
        kwargs["coaching_tier"] = tier
        if tier in ("racer", "team") and "kart_context" in sig:
            kwargs["kart_context"] = DEMO_KART
        if "vehicle_hint" in sig:
            kwargs["vehicle_hint"] = header.get("vehicle")
    t0 = time.time()
    res = services._run_analysis_pipeline_sync(str(csv_path), header["beacon_markers"], csv_path.stem, datetime.now(), **kwargs)
    return res, time.time() - t0


def problems_of(res: Dict[str, Any]) -> List[str]:
    out = []
    laps = res.get("lap_times") or []
    if not laps:
        out.append("aucun tour")
    if not res.get("corner_analysis"):
        out.append("aucun virage")
    best = res.get("best_lap_time")
    if laps and best is not None and abs(min(laps) - best) > 0.01:
        out.append(f"meilleur tour {best} ≠ min des tours {min(laps)}")
    if laps and best and best < 0.6 * sorted(laps)[len(laps) // 2]:
        out.append(f"meilleur tour {best} s anormalement court")
    ref = (res.get("circuit") or {}).get("corners_count")
    n = len(res.get("corner_analysis") or [])
    if ref and (res.get("circuit") or {}).get("confident") and n < 0.7 * ref:
        out.append(f"{n} virages détectés pour {ref} sur la fiche du circuit")
    score = (res.get("performance_score") or {}).get("overall_score")
    if score is None or not (0 <= score <= 100):
        out.append(f"score {score}")
    return out


def _clean(x):
    """NaN / infini → null, comme la réponse JSON de l'API."""
    if isinstance(x, float):
        return x if x == x and abs(x) != float("inf") else None
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


def compact(res: Dict[str, Any]) -> Dict[str, Any]:
    """Ce que lit le comparateur de l'app."""
    return _clean(_compact(res))


def _compact(res: Dict[str, Any]) -> Dict[str, Any]:
    pd = res.get("plot_data") or {}
    return {
        "best_lap_time": res.get("best_lap_time"),
        "lap_times": res.get("lap_times"),
        "corner_analysis": [
            {k: c.get(k) for k in ("corner_id", "corner_number", "apex_lat", "apex_lon", "apex_speed_real")}
            for c in res.get("corner_analysis") or []
        ],
        "plot_data": {"speed_trace": pd.get("speed_trace"), "trajectory_2d": pd.get("trajectory_2d")},
    }


def circuit_label(res: Dict[str, Any]) -> str:
    c = res.get("circuit") or {}
    if c.get("slug"):
        fit = c.get("trace_fit_m")
        return f"{c.get('name')} ({'sûr' if c.get('confident') else 'proche'}{f', écart {fit} m' if fit is not None else ''})"
    return f"non reconnu (en-tête : {(res.get('session_conditions') or {}).get('circuit_name') or '—'})"


# ───────────────────────────────────────────────────────────── main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--out", default="bench.json")
    ap.add_argument("--tiers", default="")
    ap.add_argument("--dump", default="")
    ap.add_argument("--no-compare", action="store_true")
    a = ap.parse_args()
    tiers = [t for t in a.tiers.split(",") if t] or [None]
    dump = Path(a.dump) if a.dump else None
    if dump:
        dump.mkdir(parents=True, exist_ok=True)

    files = sorted(p for d in a.folders for p in Path(d).rglob("*") if p.is_file())
    rows: List[Dict[str, Any]] = []
    out: Dict[str, Any] = {"files": {}, "formats": {}, "compare": {}}
    converted: Dict[str, Path] = {}
    by_session: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

    for f in files:
        ext = f.suffix.lower()
        if ext in ANNEX_EXT:
            from src.api.utils import validate_csv_file  # même contrôle que l'API

            class _U:  # UploadFile minimal
                filename = f.name
            msg = asyncio.run(validate_csv_file(_U(), f.read_bytes()))
            ok = bool(msg and "annexe" in msg)
            rows.append({"file": str(f.relative_to(f.parents[1])), "device": "annexe Race Studio", "import": "refusé" if ok else "ACCEPTÉ ?!",
                         "laps": "—", "circuit": "—", "problems": [] if ok else ["annexe acceptée"], "note": msg})
            print(f"{'OK ' if ok else 'ERR'} {f.name}: {msg}")
            continue
        if ext not in SESSION_EXT:
            continue
        rel = str(f.relative_to(f.parents[1]))
        try:
            csv_path = convert(f)
        except Exception as e:  # noqa: BLE001
            rows.append({"file": rel, "device": "?", "import": "ÉCHEC", "laps": 0, "circuit": "—", "problems": [f"import : {e}"]})
            print(f"ERR import {rel}: {e}")
            continue
        converted[rel] = csv_path
        device = device_of(csv_path, f)
        for tier in tiers:
            key = f"{rel}|{tier or 'actuel'}"
            try:
                res, dt = analyse(csv_path, tier)
            except Exception as e:  # noqa: BLE001
                out["files"][key] = {"file": rel, "tier": tier, "error": str(e)}
                # Refus attendu et expliqué au pilote (export coupé) : pas un défaut.
                expected = str(e).startswith("Fichier incomplet")
                if tier == tiers[0]:
                    rows.append({"file": rel, "tier": tier, "device": device, "import": "refusé" if expected else "OK",
                                 "laps": 0, "circuit": "—", "problems": [] if expected else [f"analyse : {e}"], "note": str(e)})
                print(f"{'OK ' if expected else 'ERR'} {key}: {e}")
                continue
            advice = [x for x in res.get("coaching_advice") or [] if x.get("category") != "info"]
            probs = problems_of(res)
            single = any("Un seul tour complet" in (x.get("message") or "") for x in res.get("coaching_advice") or [])
            if not advice and not single:
                probs.append("aucun conseil")
            entry = {
                "file": rel, "tier": tier, "seconds": round(dt, 1), "device": device,
                "circuit": circuit_label(res), "best_lap": res.get("best_lap_time"),
                "laps": len(res.get("lap_times") or []), "corners": res.get("corners_detected"),
                "score": (res.get("performance_score") or {}).get("overall_score"),
                "advice": res.get("coaching_advice"), "coaching_meta": res.get("coaching"), "problems": probs,
            }
            out["files"][key] = entry
            if tier == tiers[0]:
                rows.append({"file": rel, "device": device, "import": "OK", "laps": entry["laps"], "circuit": entry["circuit"],
                             "best": entry["best_lap"], "corners": entry["corners"], "score": entry["score"], "problems": probs})
                by_session[session_key(f)][ext] = entry
                if dump is not None:
                    (dump / f"{session_key(f)}{ext.replace('.', '_')}.json").write_text(json.dumps(compact(res), default=str))
            print(f"{'OK ' if not probs else 'PB '} {key:70s} {dt:5.1f}s  {entry['laps']} tours  best {entry['best_lap']}  "
                  f"{entry['corners']} virages  {len(advice)} conseils  {entry['circuit']}  {'; '.join(probs)}")

    # Mêmes séances, formats différents : mêmes chronos et mêmes virages.
    for sess, fmts in by_session.items():
        if len(fmts) < 2:
            continue
        bests = {e: v["best_lap"] for e, v in fmts.items()}
        corners = {e: v["corners"] for e, v in fmts.items()}
        laps = {e: v["laps"] for e, v in fmts.items()}
        ok = (max(bests.values()) - min(bests.values()) <= 0.05 and max(corners.values()) - min(corners.values()) <= 1
              and len(set(laps.values())) == 1)
        out["formats"][sess] = {"best": bests, "corners": corners, "laps": laps, "ok": ok}
        print(f"{'OK ' if ok else 'PB '} formats {sess}: best {bests} virages {corners} tours {laps}")

    # Comparaison : séances du même pilote le même jour (fichier aim.csv / .csv de préférence).
    if not a.no_compare:
        groups: Dict[str, List[str]] = defaultdict(list)
        for sess in by_session:
            pdk = pilot_day(sess)
            if pdk:
                groups[pdk].append(sess)
        for pdk, sessions in sorted(groups.items()):
            sessions.sort()
            for s1, s2 in zip(sessions, sessions[1:]):
                def pick(s):
                    rels = [r for r in converted if r.startswith(s + "/")]
                    return next((r for r in rels if r.endswith(".csv")), rels[0])
                try:
                    r1, _ = analyse(converted[pick(s1)], tiers[0])
                    r2, dt = analyse(converted[pick(s2)], tiers[0], light=True)
                    same = (r1.get("circuit") or {}).get("slug") == (r2.get("circuit") or {}).get("slug")
                    probs = [] if same else ["circuits différents"]
                    if not r2.get("corner_analysis"):
                        probs.append("séance 2 sans virage")
                    out["compare"][f"{s1} ↔ {s2}"] = {"best": [r1.get("best_lap_time"), r2.get("best_lap_time")],
                                                       "light_s": round(dt, 1), "problems": probs}
                    if dump is not None:
                        (dump / f"{s2}__light.json").write_text(json.dumps(compact(r2), default=str))
                    print(f"{'OK ' if not probs else 'PB '} compare {s1} ↔ {s2}: {r1.get('best_lap_time')} / {r2.get('best_lap_time')}  {'; '.join(probs)}")
                except Exception as e:  # noqa: BLE001
                    out["compare"][f"{s1} ↔ {s2}"] = {"error": str(e)}
                    print(f"ERR compare {s1} ↔ {s2}: {e}")
        if dump is not None:
            (dump / "pairs.json").write_text(json.dumps(
                [[f"{s1}_csv.json", f"{s2}__light.json"] for k in out["compare"] for s1, s2 in [k.split(" ↔ ")]], ensure_ascii=False))

    out["table"] = rows
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    bad = [r for r in rows if r.get("problems")] + [v for v in out["formats"].values() if not v["ok"]] + \
          [v for v in out["compare"].values() if v.get("problems") or v.get("error")]
    print(f"\n{len(rows)} fichiers, {len(out['formats'])} séances multi-formats, {len(out['compare'])} comparaisons — {len(bad)} problème(s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
