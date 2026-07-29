"""
Un Paddock Pass doit ouvrir les outils, pas seulement lancer un compte à rebours.

Le pass écrit son tier dans `trial_tier` / `trial_until` sans toucher à
`subscription_tier`. Tout ce qui lisait ce dernier — Mon Kart, les Réglages —
refusait donc l'accès pendant tout l'essai : le pilote voyait le bandeau et le
temps restant, mais les pages restaient verrouillées. Deux colonnes pour la même
question, et deux réponses différentes.
"""
from datetime import datetime, timedelta, timezone

import pytest

import src.core.subscription_service as ss


def _in(hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


@pytest.fixture
def profile(monkeypatch):
    """Permet de simuler un profil Supabase sans base."""
    holder = {}

    def fake_fetch(_user_id):
        return holder.get("data")

    monkeypatch.setattr(ss, "_fetch_profile", fake_fetch)
    return holder


def test_active_pass_grants_its_tier(profile):
    """Le cas qui était cassé : un pass actif doit donner l'accès."""
    profile["data"] = {
        "subscription_tier": "rookie",
        "trial_tier": "racer",
        "trial_until": _in(12),
    }
    assert ss.get_subscription_tier("u") == "racer"


def test_expired_pass_grants_nothing(profile):
    """Un essai terminé rend la main : sinon il serait à vie."""
    profile["data"] = {
        "subscription_tier": "rookie",
        "trial_tier": "racer",
        "trial_until": _in(-1),
    }
    assert ss.get_subscription_tier("u") == "rookie"


def test_pass_never_downgrades_a_subscriber(profile):
    """Un abonné Team qui essaie un pass Racer reste Team.

    L'essai ne peut que monter les droits. L'inverse ferait perdre des
    fonctionnalités à quelqu'un qui paie — le pire scénario possible.
    """
    profile["data"] = {
        "subscription_tier": "team",
        "trial_tier": "racer",
        "trial_until": _in(12),
    }
    assert ss.get_subscription_tier("u") == "team"


def test_malformed_trial_is_ignored(profile):
    """Une date absente ou illisible ne doit jamais ouvrir un accès."""
    for bad in (None, "", "pas-une-date", "2026-13-45T99:99:99"):
        profile["data"] = {
            "subscription_tier": "rookie",
            "trial_tier": "team",
            "trial_until": bad,
        }
        assert ss.get_subscription_tier("u") == "rookie", f"date acceptée : {bad!r}"


def test_unknown_trial_tier_is_ignored(profile):
    """Un tier inconnu en base ne doit pas accorder de droits arbitraires."""
    profile["data"] = {
        "subscription_tier": "rookie",
        "trial_tier": "superadmin",
        "trial_until": _in(12),
    }
    assert ss.get_subscription_tier("u") == "rookie"


def test_kart_service_uses_the_same_source(profile):
    """Mon Kart doit lire le MÊME tier que le reste de l'application.

    Sa propre implémentation interrogeait `subscription_tier` en direct : c'est
    précisément ce qui laissait les pages verrouillées pendant un essai.
    """
    from src.api.kart_service import KartService

    profile["data"] = {
        "subscription_tier": "rookie",
        "trial_tier": "racer",
        "trial_until": _in(6),
    }
    assert KartService.get_subscription_tier("u") == "racer"
