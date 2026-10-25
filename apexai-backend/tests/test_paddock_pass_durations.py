"""
Durée des Paddock Pass : de 24 h sur un circuit à 3 mois pour un pilote testeur.

Le plafond était de 720 h (un mois), trop court pour suivre un testeur sur
plusieurs week-ends de course. Il passe à 3 mois, et rien au-delà : un pass
n'est pas un abonnement gratuit.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import src.api.admin_panel_routes as admin
import src.core.subscription_service as ss


class _FakeTable:
    def __init__(self, store):
        self.store = store

    def insert(self, row):
        self.store.append(row)
        return self

    def execute(self):
        class R:
            data = [self.store[-1]] if self.store else []
        return R()


class _FakeSupabase:
    def __init__(self):
        self.rows = []

    def table(self, _name):
        return _FakeTable(self.rows)


@pytest.fixture
def fake_db(monkeypatch):
    db = _FakeSupabase()
    monkeypatch.setattr(admin, "supabase", db)
    return db


def _create(hours):
    payload = admin.PromoCreate(durationHours=hours)
    return asyncio.run(admin.create_promo_code(payload, ctx={"user_id": "owner"}))


@pytest.mark.parametrize("hours", [24, 48, 720, 1440, 2160])
def test_short_and_long_passes_are_accepted(fake_db, hours):
    res = _create(hours)
    assert res["success"] is True
    assert fake_db.rows[-1]["duration_hours"] == hours


@pytest.mark.parametrize("hours", [0, 2161, 24 * 365])
def test_out_of_range_durations_are_refused(fake_db, hours):
    with pytest.raises(HTTPException) as exc:
        _create(hours)
    assert exc.value.status_code == 400
    assert not fake_db.rows


def test_three_month_pass_still_grants_access_after_two_months(monkeypatch):
    """Un pass de 3 mois activé il y a 60 jours donne toujours accès."""
    until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    monkeypatch.setattr(ss, "_fetch_profile", lambda _uid: {
        "subscription_tier": "rookie",
        "trial_tier": "racer",
        "trial_until": until,
    })
    assert ss.get_subscription_tier("pilote") == "racer"
