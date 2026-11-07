"""
Coaching « pilote pro » : base de principes, analyse par niveaux.

Garanties :
  - chaque niveau reçoit son nombre de conseils, jamais plus ;
  - une donnée manquante (régime, eau, kart, circuit) ne bloque jamais ;
  - un conseil verrouillé ne révèle pas la consigne ;
  - Racer relie le conseil au kart (dents de couronne, pressions) ;
  - les chiffres sont écrits à la française ;
  - COACHING_ENGINE=v1 revient à l'ancien moteur.
"""
import gzip
import os
import shutil
import tempfile
from datetime import datetime

import numpy as np
import pytest

from src.analysis.coaching_pro import TIER_QUOTAS, build_kart_context, generate_pro_coaching, normalize_tier
from src.analysis.coaching_pro import fmt as F
from src.analysis.coaching_pro.context import COMPOUND_PRESSURES, select_setup
from src.analysis.coaching_pro.engine import _per_corner_filter
from src.analysis.coaching_pro.facts import CornerFacts, EngineCurve, SessionFacts
from src.analysis.coaching_pro.principles import ALL_PRINCIPLES, Ctx, Finding, p_gearing, p_pressures, p_water
from src.api.services import _run_analysis_pipeline_sync

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "adria_4laps.csv.gz")

KART = {
    "engine_model": "Rotax Max Evo", "tires_model": "Vega Rouge (SL4)", "driver_weight_kg": 70,
    "setup": {"cold_pressure_front": 0.95, "cold_pressure_rear": 0.95, "sprocket_front": 12, "sprocket_rear": 80,
              "track_width_rear": 1400},
}


@pytest.fixture(scope="module")
def csv_path():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        path = tmp.name
    with gzip.open(FIXTURE, "rb") as f_in, open(path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    yield path
    os.unlink(path)


def _run(path, tier, kart=None):
    return _run_analysis_pipeline_sync(path, [], f"t-{tier}", datetime.now(), track_condition="dry",
                                       track_temperature=24.0, coaching_tier=tier, kart_context=kart)


@pytest.fixture(scope="module")
def by_tier(csv_path):
    return {t: _run(csv_path, t, KART if t == "racer" else None) for t in ("visitor", "rookie", "racer")}


def _real(items):
    return [a for a in items if a.get("category") not in ("info", "plan") and not a.get("locked")]


def test_quota_per_tier(by_tier):
    for t, res in by_tier.items():
        assert res["coaching"]["tier"] == t
        assert len(_real(res["coaching_advice"])) <= TIER_QUOTAS[t]
    assert TIER_QUOTAS["visitor"] < TIER_QUOTAS["rookie"] < TIER_QUOTAS["racer"]


def test_locked_items_hide_the_how(by_tier):
    for t in ("visitor", "rookie"):
        for a in by_tier[t]["coaching_advice"]:
            if a.get("locked"):
                assert a["explanation"] == "" and not a.get("action")
                assert a["tier_required"] in ("rookie", "racer")
    assert not any(a.get("locked") for a in by_tier["racer"]["coaching_advice"])


def test_numbers_are_french(by_tier):
    import re
    for res in by_tier.values():
        for a in _real(res["coaching_advice"]):
            txt = a["message"] + " " + a["explanation"]
            assert not re.search(r"\d\.\d+\s*(?:s|g|m|km/h|bar)\b", txt), txt


def test_missing_channels_never_block(csv_path):
    import pandas as pd
    df = pd.read_csv(csv_path, skiprows=14, low_memory=False)
    assert len(df) > 100  # le fichier se lit
    # Sans régime ni eau ni kart : l'analyse reste complète.
    tmp = csv_path + ".norpm.csv"
    with open(csv_path, encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()
    hdr_i = next(i for i, ln in enumerate(lines) if ln.startswith('"Time"'))
    cols = [c.strip('"') for c in lines[hdr_i].split(",")]
    drop = {i for i, c in enumerate(cols) if c.lower() in ("rpm", "water temp", "exhaust temp")}
    out = lines[:hdr_i] + [",".join(v for i, v in enumerate(ln.split(",")) if i not in drop) for ln in lines[hdr_i:]]
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    try:
        res = _run(tmp, "racer", None)
        assert res["coaching"]["uses"]["engine_curve"] is False
        assert res["coaching"]["uses"]["kart"] is False
        assert res["coaching_advice"], "il faut au moins l'encart de contexte"
    finally:
        os.unlink(tmp)


def test_kill_switch_v1(csv_path, monkeypatch):
    monkeypatch.setenv("COACHING_ENGINE", "v1")
    res = _run(csv_path, "racer", KART)
    assert res.get("coaching") is None
    assert not any(a.get("locked") for a in res["coaching_advice"])


def test_every_principle_is_documented():
    for p in ALL_PRINCIPLES:
        assert p.doctrine and p.measures and p.min_tier in ("visitor", "rookie", "racer")


def test_normalize_tier():
    assert normalize_tier(None) == "visitor"
    assert normalize_tier("team") == "racer"
    assert normalize_tier("weird") == "rookie"


def test_french_numbers():
    assert F.num(1234.5, 1) == "1\u202f234,5"
    assert F.sec(0.25) == "0,25\u00a0s"
    assert F.rpm(8253) == "8\u202f250\u00a0tr/min"


# ── Principes Racer, sur des faits construits à la main ────────────────────────

class _Cond:
    condition = "dry"
    label = "Sèche"
    allow_brake_later = True
    allow_speed_push = True


def _corner(i, kind="epingle", rpm=6500, rpm_best=7000):
    return CornerFacts(id=i, direction="à droite", kind=kind, kind_source="circuit", angle_deg=180, radius_m=10,
                       pos_m=100.0 * i, to_next_m=150, straight_after_m=80, opens_longest_straight=False,
                       time_lost=0.1, best_lap_here=3, recurring=True, lap_spread_s=0.2, apex_speed=50,
                       apex_speed_best=52, apex_error_m=0.5, apex_error_dir=None, entry_speed=90, lateral_g=1.6,
                       raw={}, rpm_min=rpm, rpm_min_best=rpm_best)


def _ctx(tier="racer", kart=KART, plateau=0.0, top=13000.0, water=None):
    eng = EngineCurve(bins=[{"rpm": r, "g": g, "n": 50} for r, g in
                            [(6750, 0.30), (7750, 0.38), (8750, 0.45), (9750, 0.44), (11750, 0.30), (13250, 0.1)]],
                      peak_rpm=8750, peak_g=0.45, knee_rpm=8750, top_rpm=top, top_plateau_s=plateau)
    sf = SessionFacts(laps_used=list(range(1, 9)), lap_times={i: 50 + i * 0.01 for i in range(1, 9)}, best_lap=1,
                      best_lap_time=50.01, median_lap_time=50.05, ideal_gain_s=0.3, vmax=110, has_rpm=True,
                      has_water=bool(water), engine=eng, water_by_lap=water or {})
    k = build_kart_context(select_setup(kart, None)) if kart else None
    fam = (k.engine if k else {}) or {"top": 13800, "cooling": "liquide"}
    return Ctx(tier=tier, session=sf, corners=[_corner(1), _corner(2), _corner(3, "moyen", 9000, 9100)],
               kart=k, conditions=_Cond(), voice=F.Voice("t"), engine_family=fam)


def test_gearing_long_gives_teeth_for_racer():
    f = p_gearing(_ctx())
    assert f and f.min_tier == "racer"
    assert "80 →" in f.action and "dents" in f.action


def test_gearing_short_when_stuck_at_top():
    f = p_gearing(_ctx(plateau=0.8, top=13900))
    assert f and "trop courte" in f.headline and "80 → 79" in f.action


def test_gearing_without_kart_has_no_teeth():
    f = p_gearing(_ctx(tier="rookie", kart=None))
    assert f and "→" not in f.action


def test_pressures_out_of_range_for_compound():
    f = p_pressures(_ctx())
    lo, hi = COMPOUND_PRESSURES["medium"]["dry"]
    assert f and "trop hautes" in f.headline
    assert F.bar(hi) in f.fact


def test_water_cold():
    f = p_water(_ctx(water={i: 40.0 + i for i in range(1, 9)}))
    assert f and "froid" in f.headline and "radiateur" in f.action


def test_one_finding_per_basis_per_corner():
    a = Finding("vitesse_corde", "trajectoire", "speed", 4, "a", "f", "x", rank_s=0.2, lever="elan")
    b = Finding("frein_effleurement", "freinage", "speed", 4, "b", "f", "y", rank_s=0.19, lever="pied_constant")
    c = Finding("sortie", "sortie", "exit", 4, "c", "f", "z", rank_s=0.1, lever="enrouler")
    kept = _per_corner_filter([a, b, c])
    assert [k.principle for k in kept] == ["vitesse_corde", "sortie"]
