"""Accès donné par une structure Team : jamais sans l'interrupteur, jamais à la baisse."""
from datetime import datetime, timedelta, timezone

import src.core.subscription_service as ss
import src.core.team_service as ts


def _in(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self):
        return type("R", (), {"data": self.rows})()


class FakeSB:
    def __init__(self, flag, members):
        self.flag, self.members = flag, members
    def table(self, name):
        if name == "app_flags":
            return FakeQuery([{"enabled": self.flag}] if self.flag is not None else [])
        return FakeQuery(self.members)


def member(role, status="essai", until=10):
    return {"role": role, "status": "actif", "structures": {"status": status, "trial_until": _in(until), "contract_until": None}}


def test_switch_off_grants_nothing():
    assert ts.structure_tier("u", FakeSB(False, [member("pilote")])) is None
    assert ts.structure_tier("u", FakeSB(None, [member("pilote")])) is None


def test_pilot_gets_racer_coach_gets_team():
    assert ts.structure_tier("u", FakeSB(True, [member("pilote")])) == "racer"
    assert ts.structure_tier("u", FakeSB(True, [member("pilote"), member("coach")])) == "team"


def test_expired_or_finished_structure_grants_nothing():
    assert ts.structure_tier("u", FakeSB(True, [member("pilote", until=-1)])) is None
    assert ts.structure_tier("u", FakeSB(True, [member("pilote", status="terminee")])) is None
    assert ts.structure_tier("u", FakeSB(True, [member("pilote", status="suspendue")])) is None


def test_emergency_off(monkeypatch):
    monkeypatch.setenv("TEAM_SPACE_FORCE_OFF", "1")
    assert ts.structure_tier("u", FakeSB(True, [member("coach")])) is None


def test_structure_access_only_raises_tier():
    assert ss._effective_tier({"subscription_tier": "rookie", "_structure_tier": "racer"}) == "racer"
    assert ss._effective_tier({"subscription_tier": "team", "_structure_tier": "racer"}) == "team"
    assert ss._effective_tier({"subscription_tier": "rookie", "_structure_tier": None}) == "rookie"
    assert ss._effective_tier({"subscription_tier": "rookie", "_structure_tier": "bidon"}) == "rookie"
