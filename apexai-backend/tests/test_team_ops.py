"""Règles de l'espace Team : demandes, structures, adhésion, départ, vue équipe."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.core import team_ops as T
from src.core.team_ops import TeamError


def _iso(days: float = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class MemStore:
    def __init__(self):
        self.t = {k: [] for k in ("contact_requests", "structures", "structure_members", "structure_invites",
                                  "shared_analyses", "analyses", "profiles")}
        self.emails = {}

    def insert(self, table, row):
        row = dict(row)
        if table in ("contact_requests", "structures") and "id" not in row:
            row["id"] = str(uuid.uuid4())
        row.setdefault("created_at", _iso())
        if table == "structure_invites":
            row.setdefault("uses", 0)
            row.setdefault("revoked", False)
        self.t[table].append(row)
        return row

    def _match(self, r, m):
        return all(r.get(k) == v for k, v in (m or {}).items())

    def update(self, table, match, fields):
        for r in self.t[table]:
            if self._match(r, match):
                r.update(fields)

    def select(self, table, match=None, columns="*", order=None, desc=False, limit=None):
        rows = [dict(r) for r in self.t[table] if self._match(r, match)]
        if order:
            rows.sort(key=lambda r: r.get(order) or "", reverse=desc)
        return rows[:limit] if limit else rows

    def select_in(self, table, column, values, columns="*", since=None):
        vals = set(values)
        return [dict(r) for r in self.t[table] if r.get(column) in vals and (not since or r.get("created_at", "") >= since)]

    def delete(self, table, match):
        self.t[table] = [r for r in self.t[table] if not self._match(r, match)]

    def user_email(self, user_id):
        return self.emails.get(user_id)


@pytest.fixture
def world():
    st = MemStore()
    admin, coach, p1, p2 = "admin", "coach", "p1", "p2"
    st.emails[coach] = "coach@ecole.fr"
    for uid, name in ((coach, "Arthur Coach"), (p1, "Léo Martin"), (p2, "Inès Durand")):
        st.t["profiles"].append({"id": uid, "full_name": name, "subscription_tier": "rookie"})
    out = T.admin_create_structure(st, admin, {"name": "École Test", "coach_email": "coach@ecole.fr"})
    sid = out["structure"]["id"]
    T.join(st, coach, out["coach_invite"]["code"], consent=False)
    return st, sid


# ───────────────────────────────────────────── demandes

def test_contact_request_validated_and_throttled():
    st = MemStore()
    with pytest.raises(TeamError):
        T.create_contact_request(st, {"name": "A", "email": "pas-un-email"})
    for _ in range(3):
        T.create_contact_request(st, {"name": "A", "email": "a@b.fr", "kind": "ecole"})
    with pytest.raises(TeamError) as e:
        T.create_contact_request(st, {"name": "A", "email": "A@b.fr"})
    assert e.value.status == 429


# ───────────────────────────────────────────── structures et adhésion

def test_structure_trial_defaults_to_four_weeks(world):
    st, sid = world
    s = st.select("structures", {"id": sid})[0]
    until = datetime.fromisoformat(s["trial_until"])
    assert 27 <= (until - datetime.now(timezone.utc)).days <= 28
    assert s["max_pilots"] is None  # au devis : pas de limite par défaut


def test_coach_invite_is_reserved_to_its_email(world):
    st, sid = world
    out = T.admin_create_structure(st, "admin", {"name": "Autre", "coach_email": "x@y.fr"})
    st.emails["intrus"] = "intrus@y.fr"
    with pytest.raises(TeamError) as e:
        T.join(st, "intrus", out["coach_invite"]["code"], consent=False)
    assert e.value.status == 403


def test_pilot_needs_explicit_consent(world):
    st, sid = world
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    with pytest.raises(TeamError):
        T.join(st, "p1", code, consent=False)
    T.join(st, "p1", code, consent=True)
    m = st.select("structure_members", {"user_id": "p1"})[0]
    assert m["status"] == "actif" and m["consent_at"] and m["consent_version"] == T.CONSENT_VERSION


def test_guardian_certification_comes_from_the_coach_code(world):
    st, sid = world
    code = T.create_pilot_invite(st, "coach", sid, {"guardian_certified": True})["code"]
    T.join(st, "p1", code, consent=True)
    m = st.select("structure_members", {"user_id": "p1"})[0]
    assert m["guardian_certified_by"] == "coach" and m["guardian_certified_at"]


def test_only_a_coach_can_create_codes(world):
    st, sid = world
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    T.join(st, "p1", code, consent=True)
    with pytest.raises(TeamError) as e:
        T.create_pilot_invite(st, "p1", sid, {})
    assert e.value.status == 403


def test_seat_limit_and_expired_codes(world):
    st, sid = world
    T.admin_update_structure(st, sid, {"max_pilots": 1})
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    T.join(st, "p1", code, consent=True)
    with pytest.raises(TeamError) as e:
        T.join(st, "p2", code, consent=True)
    assert e.value.status == 409
    st.update("structure_invites", {"code": code}, {"expires_at": _iso(-1)})
    with pytest.raises(TeamError) as e:
        T.invite_info(st, code)
    assert e.value.status == 410


def test_expired_structure_refuses_members_and_coach(world):
    st, sid = world
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    T.admin_update_structure(st, sid, {"trial_until": _iso(-1)})
    with pytest.raises(TeamError):
        T.join(st, "p1", code, consent=True)
    with pytest.raises(TeamError):
        T.team_overview(st, "coach", sid)


# ───────────────────────────────────────────── départ

def test_leaving_keeps_history_and_offers_a_racer_month(world):
    st, sid = world
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    T.join(st, "p1", code, consent=True)
    res = T.leave(st, "p1", sid)
    m = st.select("structure_members", {"user_id": "p1"})[0]
    assert m["status"] == "parti" and m["left_at"]
    prof = st.select("profiles", {"id": "p1"})[0]
    assert prof["trial_tier"] == "racer" and res["racer_until"]
    assert 29 <= (datetime.fromisoformat(prof["trial_until"]) - datetime.now(timezone.utc)).days <= 30


def test_paying_racer_gets_no_gift(world):
    st, sid = world
    st.update("profiles", {"id": "p1"}, {"subscription_tier": "racer"})
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    T.join(st, "p1", code, consent=True)
    assert T.leave(st, "p1", sid)["racer_until"] is None


def test_coach_removing_a_pilot(world):
    st, sid = world
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    T.join(st, "p1", code, consent=True)
    T.remove_pilot(st, "coach", sid, "p1")
    assert st.select("structure_members", {"user_id": "p1"})[0]["status"] == "retire"
    with pytest.raises(TeamError):
        T.pilot_sessions(st, "coach", sid, "p1")


def test_rejoin_after_leaving_restarts_history_window(world):
    st, sid = world
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    T.join(st, "p1", code, consent=True)
    T.leave(st, "p1", sid)
    T.join(st, "p1", code, consent=True)
    m = st.select("structure_members", {"user_id": "p1"})[0]
    assert m["status"] == "actif" and m["left_at"] is None


# ───────────────────────────────────────────── partage et vue équipe

def test_share_only_own_sessions(world):
    st, sid = world
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    T.join(st, "p1", code, consent=True)
    st.t["analyses"].append({"id": "a_p2", "user_id": "p2", "created_at": _iso(-40)})
    with pytest.raises(TeamError):
        T.share_analysis(st, "p1", sid, "a_p2")


def test_team_overview_respects_history_window(world):
    st, sid = world
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    T.join(st, "p1", code, consent=True)
    T.join(st, "p2", code, consent=True)
    st.t["analyses"] += [
        {"id": "old", "user_id": "p1", "created_at": _iso(-60), "circuit_name": "Ancenis", "best_lap_time": 53.4},
        {"id": "old_shared", "user_id": "p1", "created_at": _iso(-50), "circuit_name": "Ancenis", "best_lap_time": 53.0},
        {"id": "new", "user_id": "p1", "created_at": _iso(1), "circuit_name": "Ancenis", "best_lap_time": 52.6},
        {"id": "p2new", "user_id": "p2", "created_at": _iso(1), "circuit_name": "Ancenis", "best_lap_time": 53.1},
    ]
    T.share_analysis(st, "p1", sid, "old_shared")
    ov = T.team_overview(st, "coach", sid)
    leo = next(p for p in ov["pilots"] if p["user_id"] == "p1")
    assert leo["name"] == "Léo"              # prénom du COMPTE, jamais du fichier
    assert leo["sessions"] == 2              # « old » (avant l'arrivée, non partagée) exclue
    assert leo["trend_30d"] == pytest.approx(-0.4)
    rk = ov["rankings"][0]
    assert rk["circuit"] == "Ancenis" and [r["name"] for r in rk["rows"]] == ["Léo", "Inès"]
    ids = {s["id"] for s in T.pilot_sessions(st, "coach", sid, "p1")["sessions"]}
    assert ids == {"new", "old_shared"}


def test_pilot_cannot_read_team_overview(world):
    st, sid = world
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    T.join(st, "p1", code, consent=True)
    with pytest.raises(TeamError) as e:
        T.team_overview(st, "p1", sid)
    assert e.value.status == 403


def test_admin_overview_counts(world):
    st, sid = world
    code = T.create_pilot_invite(st, "coach", sid, {})["code"]
    T.join(st, "p1", code, consent=True)
    ov = T.admin_overview(st)
    s = ov["structures"][0]
    assert s["coaches"] == 1 and s["pilots"] == 1 and s["live"]
