"""
Les conditions de piste doivent changer la PHYSIQUE de l'analyse.

L'état de piste et la température étaient demandés au pilote, affichés en tête
du rapport… et n'influençaient aucun calcul. Pire : la ligne de course bornait
l'adhérence à μ ≥ 1,00 même sous la pluie, où un kart tient environ 0,7 — elle
proposait donc des vitesses de passage inatteignables, puis reprochait au pilote
de ne pas les atteindre.

Ces tests interdisent le retour à une option décorative.
"""
import gzip
import os
import shutil
import tempfile
from datetime import datetime

import pytest

from src.analysis.conditions import resolve_conditions, get_conditions, attach_conditions
from src.api.services import _run_analysis_pipeline_sync

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "adria_4laps.csv.gz")


# ── Le modèle de conditions ─────────────────────────────────────────────────

def test_grip_decreases_from_dry_to_rain():
    """Plus la piste est mouillée, moins il y a d'adhérence. Sans exception."""
    mus = [resolve_conditions(c).mu_reference for c in ("dry", "damp", "wet", "rain")]
    assert mus == sorted(mus, reverse=True), f"μ non décroissant : {mus}"
    assert mus[0] > mus[-1] * 1.5, "l'écart sec/pluie doit être significatif"


def test_braking_floor_follows_conditions():
    """Un freinage à 0,5 g est mou au sec, correct sous la pluie.

    Sans ce plancher variable, chaque virage d'une séance pluie serait signalé
    comme « freinage trop mou » — un rapport entièrement faux.
    """
    dry = resolve_conditions("dry")
    rain = resolve_conditions("rain")
    assert rain.braking_min_g < dry.braking_min_g
    assert rain.braking_min_g < 0.5 < dry.braking_min_g


def test_wet_conditions_forbid_dangerous_advice():
    """« Freine plus tard » sur piste mouillée est un conseil dangereux."""
    assert resolve_conditions("dry").allow_brake_later is True
    assert resolve_conditions("damp").allow_brake_later is True
    assert resolve_conditions("wet").allow_brake_later is False
    assert resolve_conditions("rain").allow_brake_later is False
    # Sous la pluie, une vitesse de passage cible n'a plus de sens.
    assert resolve_conditions("rain").allow_speed_push is False


def test_temperature_modulates_grip_without_replacing_it():
    """La température module l'adhérence ; elle ne la transforme pas.

    Une piste sèche à 5 °C reste plus adhérente qu'une piste mouillée à 25 °C :
    confondre les deux effets produirait des objectifs absurdes.
    """
    cold_dry = resolve_conditions("dry", 5.0)
    warm_dry = resolve_conditions("dry", 25.0)
    warm_wet = resolve_conditions("wet", 25.0)
    assert cold_dry.mu_reference < warm_dry.mu_reference
    assert cold_dry.mu_reference > warm_wet.mu_reference


def test_unknown_condition_falls_back_to_dry():
    """Une valeur inconnue ne doit jamais produire une adhérence nulle."""
    c = resolve_conditions("brouillard-givrant", None)
    assert c.condition == "dry"
    assert c.mu_reference > 0.5


def test_conditions_are_readable_from_the_dataframe():
    """Le pipeline lit les conditions sur la session, pas dans ses paramètres."""
    import pandas as pd

    df = pd.DataFrame({"speed": [50.0, 60.0]})
    assert get_conditions(df).condition == "dry"  # défaut sûr
    attach_conditions(df, "rain", 12.0)
    assert get_conditions(df).condition == "rain"
    assert get_conditions(df).mu_reference < 1.0


def test_summary_explains_what_changed():
    """Le pilote doit LIRE ce que son choix a modifié, sinon rien ne le prouve."""
    c = resolve_conditions("wet", 14.0)
    txt = c.summary()
    assert "adhérence" in txt.lower()
    # La valeur citée est exactement celle utilisée par le calcul, en notation
    # française : un rapport qui écrit « 0.91 » puis « 1,30 » fait négligé.
    assert f"{c.mu_reference:.2f}".replace(".", ",") in txt
    import re
    assert not re.search(r"\d\.\d", txt), f"point décimal anglais dans : {txt}"


# ── Effet réel sur une analyse complète ─────────────────────────────────────

def _run(condition, temperature):
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        path = tmp.name
    with gzip.open(FIXTURE, "rb") as f_in, open(path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    try:
        return _run_analysis_pipeline_sync(
            path, [], f"test-{condition}", datetime.now(),
            track_condition=condition, track_temperature=temperature,
        )
    finally:
        os.unlink(path)


@pytest.fixture(scope="module")
def dry_analysis():
    return _run("dry", 24.0)


@pytest.fixture(scope="module")
def rain_analysis():
    return _run("rain", 11.0)


def test_resolved_conditions_are_returned_to_the_client(dry_analysis, rain_analysis):
    """Sans ces valeurs dans la réponse, rien ne prouve à l'écran que le choix sert."""
    for analysis, expected in ((dry_analysis, "dry"), (rain_analysis, "rain")):
        resolved = (analysis.get("session_conditions") or {}).get("resolved")
        assert resolved, "conditions résolues absentes de la réponse"
        assert resolved["condition"] == expected
        assert resolved["summary"]
    dry = dry_analysis["session_conditions"]["resolved"]
    rain = rain_analysis["session_conditions"]["resolved"]
    assert rain["mu_reference"] < dry["mu_reference"]
    assert rain["braking_min_g"] < dry["braking_min_g"]


def test_rain_never_advises_to_brake_later(rain_analysis):
    """Aucun conseil de la séance pluie ne doit pousser à retarder un freinage."""
    for a in rain_analysis["coaching_advice"]:
        msg = (a.get("message") or "").lower()
        assert "plus tard" not in msg, f"conseil dangereux sous la pluie : {a['message']}"


def test_rain_drops_target_speed_advice(rain_analysis):
    """Sous la pluie, une vitesse de passage cible n'est pas exploitable."""
    cats = {a.get("category") for a in rain_analysis["coaching_advice"]}
    assert "speed" not in cats


def test_ideal_lap_stays_attainable_whatever_the_declared_conditions(
    dry_analysis, rain_analysis
):
    """Le « tour parfait » ne peut jamais être plus lent que le meilleur tour réel.

    C'est le garde-fou qui rattrape une case cochée par erreur : sans lui,
    déclarer « pluie » sur une séance sèche affichait un objectif plus lent que
    ce que le pilote venait de réaliser.
    """
    for analysis in (dry_analysis, rain_analysis):
        rl = analysis.get("racing_line")
        if not rl:
            continue
        best_real = float(analysis.get("best_lap_time") or 0)
        if best_real <= 0:
            continue
        assert float(rl["optimal_lap_time_s"]) <= best_real + 1e-6, (
            f"tour idéal {rl['optimal_lap_time_s']}s plus lent que le réel {best_real}s"
        )


def test_declared_conditions_contradicting_data_are_reported(rain_analysis):
    """Une séance sèche déclarée « pluie » doit être signalée, pas corrigée en silence."""
    rl = rain_analysis.get("racing_line") or {}
    assert rl.get("conditions_mismatch") is True
    messages = " ".join(a.get("message", "") for a in rain_analysis["coaching_advice"])
    assert "ne le confirme pas" in messages
