"""
Sécurité de l'espace Team : un coach ne voit QUE ce qu'il doit voir.

Ces tests rejouent les politiques RLS sur un vrai Postgres (Supabase simulé :
rôles, auth.uid()). Ils tournent si une base est joignable :
  - APEX_RLS_DSN (ex. CI : postgresql://postgres@localhost:5432/postgres)
  - sinon le Postgres local de dev (socket /var/lib/postgresql/apextest, port 54329)
Sinon ils sont ignorés.
"""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase/migrations/20261118010000_team_space.sql"
DOWN = ROOT / "supabase/migrations/20261118010000_team_space.down.sql"
# Étapes suivantes de l'espace Team, appliquées dans l'ordre après le socle.
LATER = sorted(p for p in (ROOT / "supabase/migrations").glob("2026111802*_team*.sql") if not p.name.endswith(".down.sql"))
STUB = Path(__file__).with_name("supabase_stub.sql")
DSN = os.environ.get("APEX_RLS_DSN") or "host=/var/lib/postgresql/apextest port=54329 user=postgres dbname=postgres"


def _admin_conn(dbname: str = "postgres"):
    conn = psycopg2.connect(DSN) if dbname == "postgres" else psycopg2.connect(_with_db(DSN, dbname))
    conn.autocommit = True
    return conn


def _with_db(dsn: str, dbname: str) -> str:
    if "://" in dsn:
        base = dsn.rsplit("/", 1)[0]
        return f"{base}/{dbname}"
    parts = [p for p in dsn.split() if not p.startswith("dbname=")]
    return " ".join(parts + [f"dbname={dbname}"])


@pytest.fixture(scope="module")
def db():
    try:
        root = _admin_conn()
    except Exception as exc:  # pas de Postgres : on n'invente pas un succès
        pytest.skip(f"Postgres de test indisponible : {exc}")
    name = f"apex_rls_{uuid.uuid4().hex[:8]}"
    with root.cursor() as c:
        c.execute(f'CREATE DATABASE "{name}"')
    conn = _admin_conn(name)
    with conn.cursor() as c:
        c.execute(STUB.read_text())
        c.execute(MIGRATION.read_text())
        for m in LATER:
            c.execute(m.read_text())
    yield conn
    conn.close()
    with root.cursor() as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    root.close()


U = {k: str(uuid.uuid4()) for k in (
    "coachA", "coachA_gone", "p1", "p2_gone", "p3_B", "coachB", "p4", "outsider", "coach_pilot")}
S_A, S_B = str(uuid.uuid4()), str(uuid.uuid4())


@pytest.fixture(scope="module")
def seeded(db):
    with db.cursor() as c:
        for k, v in U.items():
            c.execute("INSERT INTO auth.users (id, email) VALUES (%s, %s)", (v, f"{k}@test.local"))
        c.execute("""INSERT INTO public.structures (id, name, status, trial_until)
                     VALUES (%s, 'Ecole A', 'essai', now() + interval '20 days'),
                            (%s, 'Club B',  'active', NULL)""", (S_A, S_B))
        rows = [
            (S_A, U["coachA"], "coach", "actif", None, "now() - interval '30 days'"),
            (S_A, U["coachA_gone"], "coach", "parti", None, "now() - interval '30 days'"),
            (S_A, U["p1"], "pilote", "actif", "now()", "now() - interval '10 days'"),
            (S_A, U["p2_gone"], "pilote", "parti", "now()", "now() - interval '10 days'"),
            (S_A, U["p4"], "pilote", "actif", "now()", "now() - interval '10 days'"),
            (S_B, U["coachB"], "coach", "actif", None, "now() - interval '30 days'"),
            (S_B, U["p3_B"], "pilote", "actif", "now()", "now() - interval '10 days'"),
            # Un coach de B aussi pilote de A : ne doit rien voir de A.
            (S_A, U["coach_pilot"], "pilote", "actif", "now()", "now() - interval '10 days'"),
            (S_B, U["coach_pilot"], "coach", "actif", None, "now() - interval '30 days'"),
        ]
        for s, u, role, status, consent, joined in rows:
            c.execute(
                f"INSERT INTO public.structure_members (structure_id, user_id, role, status, consent_at, joined_at) "
                f"VALUES (%s, %s, %s, %s, {consent or 'NULL'}, {joined})", (s, u, role, status))
        analyses = [
            ("p1_old", "p1", "now() - interval '40 days'"),
            ("p1_old_shared", "p1", "now() - interval '40 days'"),
            ("p1_new", "p1", "now() - interval '2 days'"),
            ("p2_new", "p2_gone", "now() - interval '2 days'"),
            ("p3_new", "p3_B", "now() - interval '2 days'"),
            ("p4_new", "p4", "now() - interval '2 days'"),
            ("coachA_own", "coachA", "now() - interval '2 days'"),
            ("outsider_own", "outsider", "now() - interval '2 days'"),
            ("cp_new", "coach_pilot", "now() - interval '2 days'"),
        ]
        for aid, owner, created in analyses:
            c.execute(f"INSERT INTO public.analyses (id, user_id, created_at) VALUES (%s, %s, {created})", (aid, U[owner]))
        c.execute("INSERT INTO public.shared_analyses (structure_id, analysis_id, pilot_id) VALUES (%s, 'p1_old_shared', %s)", (S_A, U["p1"]))
        # Partage forgé : une séance de p1 « partagée » au nom de p4 ne doit rien ouvrir.
        c.execute("INSERT INTO public.shared_analyses (structure_id, analysis_id, pilot_id) VALUES (%s, 'p1_old', %s)", (S_A, U["p4"]))
        c.execute("INSERT INTO public.coach_notes (structure_id, pilot_id, author_id, kind, body) VALUES (%s, %s, %s, 'note', 'Freine plus tard au V4')", (S_A, U["p1"], U["coachA"]))
        c.execute("INSERT INTO public.coach_notes (structure_id, pilot_id, author_id, kind, body) VALUES (%s, %s, %s, 'objectif', 'Régularité')", (S_A, U["p2_gone"], U["coachA"]))
    return db


def _flag(db, on: bool):
    with db.cursor() as c:
        c.execute("UPDATE public.app_flags SET enabled = %s WHERE key = 'team_space'", (on,))


@contextmanager
def as_user(db, who: str):
    """Exécute en tant qu'utilisateur connecté de l'app (rôle authenticated)."""
    c = db.cursor()
    c.execute("BEGIN")
    c.execute("SET LOCAL ROLE authenticated")
    c.execute("SELECT set_config('request.jwt.claim.sub', %s, true)", (U[who],))
    try:
        yield c
    finally:
        c.execute("ROLLBACK")
        c.close()


def visible(db, who: str, table: str = "analyses", col: str = "id") -> set:
    with as_user(db, who) as c:
        c.execute(f"SELECT {col} FROM public.{table}")
        return {r[0] for r in c.fetchall()}


# ─────────────────────────────────────────────────────────────── séances

def test_switch_off_coach_sees_only_his_own(seeded):
    _flag(seeded, False)
    assert visible(seeded, "coachA") == {"coachA_own"}


def test_coach_sees_exactly_his_active_pilots_since_joining(seeded):
    _flag(seeded, True)
    assert visible(seeded, "coachA") == {"coachA_own", "p1_new", "p1_old_shared", "p4_new", "cp_new"}


def test_never_other_structure_or_departed_pilot_or_old_session(seeded):
    _flag(seeded, True)
    seen = visible(seeded, "coachA")
    for forbidden in ("p1_old", "p2_new", "p3_new", "outsider_own"):
        assert forbidden not in seen


def test_other_coach_sees_only_his_structure(seeded):
    _flag(seeded, True)
    assert visible(seeded, "coachB") == {"p3_new"}


def test_coach_of_B_who_is_pilot_in_A_sees_nothing_of_A(seeded):
    _flag(seeded, True)
    assert visible(seeded, "coach_pilot") == {"cp_new", "p3_new"}


def test_pilots_see_only_their_own_sessions(seeded):
    _flag(seeded, True)
    assert visible(seeded, "p1") == {"p1_old", "p1_old_shared", "p1_new"}
    assert visible(seeded, "p4") == {"p4_new"}
    assert visible(seeded, "outsider") == {"outsider_own"}


def test_departed_coach_sees_nothing(seeded):
    _flag(seeded, True)
    assert visible(seeded, "coachA_gone") == set()


def test_expired_trial_or_suspended_structure_closes_access(seeded):
    _flag(seeded, True)
    with seeded.cursor() as c:
        c.execute("UPDATE public.structures SET trial_until = now() - interval '1 day' WHERE id = %s", (S_A,))
    try:
        assert visible(seeded, "coachA") == {"coachA_own"}
    finally:
        with seeded.cursor() as c:
            c.execute("UPDATE public.structures SET trial_until = now() + interval '20 days' WHERE id = %s", (S_A,))
    with seeded.cursor() as c:
        c.execute("UPDATE public.structures SET status = 'suspendue' WHERE id = %s", (S_B,))
    try:
        assert visible(seeded, "coachB") == set()
    finally:
        with seeded.cursor() as c:
            c.execute("UPDATE public.structures SET status = 'active' WHERE id = %s", (S_B,))


def test_pilot_leaving_closes_access_immediately(seeded):
    _flag(seeded, True)
    with seeded.cursor() as c:
        c.execute("UPDATE public.structure_members SET status = 'parti', left_at = now() WHERE structure_id = %s AND user_id = %s", (S_A, U["p4"]))
    try:
        assert "p4_new" not in visible(seeded, "coachA")
    finally:
        with seeded.cursor() as c:
            c.execute("UPDATE public.structure_members SET status = 'actif', left_at = NULL WHERE structure_id = %s AND user_id = %s", (S_A, U["p4"]))


def test_coach_cannot_write_pilot_sessions(seeded):
    _flag(seeded, True)
    with as_user(seeded, "coachA") as c:
        c.execute("UPDATE public.analyses SET circuit_name = 'x' WHERE id = 'p1_new'")
        assert c.rowcount == 0
        c.execute("DELETE FROM public.analyses WHERE id = 'p1_new'")
        assert c.rowcount == 0
    with as_user(seeded, "coachA") as c:
        with pytest.raises(psycopg2.Error):
            c.execute("INSERT INTO public.analyses (id, user_id) VALUES ('forged', %s)", (U["p1"],))


# ─────────────────────────────────────────────────────────────── tables Team

def test_membership_visibility(seeded):
    _flag(seeded, True)
    assert visible(seeded, "p1", "structure_members", "user_id") == {U["p1"]}
    coach_view = visible(seeded, "coachA", "structure_members", "user_id")
    assert coach_view == {U["coachA"], U["p1"], U["p4"], U["coach_pilot"]}
    assert visible(seeded, "outsider", "structure_members", "user_id") == set()


def test_members_cannot_write_team_tables(seeded):
    _flag(seeded, True)
    for sql, args in (
        ("INSERT INTO public.structure_members (structure_id, user_id, role, status) VALUES (%s, %s, 'coach', 'actif')", (S_A, U["outsider"])),
        ("UPDATE public.structures SET status = 'active'", ()),
        ("INSERT INTO public.shared_analyses (structure_id, analysis_id, pilot_id) VALUES (%s, 'p1_old', %s)", (S_A, U["p1"])),
        ("INSERT INTO public.coach_notes (structure_id, pilot_id, body) VALUES (%s, %s, 'x')", (S_A, U["p1"])),
    ):
        with as_user(seeded, "coachA") as c:
            try:
                c.execute(sql, args)
                assert c.rowcount == 0, sql
            except psycopg2.Error:
                pass


def test_private_tables_are_closed_to_the_app(seeded):
    _flag(seeded, True)
    for table, col in (("contact_requests", "id"), ("structure_invites", "code"), ("app_flags", "key")):
        assert visible(seeded, "coachA", table, col) == set()


def test_notes_follow_the_pilot(seeded):
    _flag(seeded, True)
    assert len(visible(seeded, "p1", "coach_notes")) == 1
    assert len(visible(seeded, "p2_gone", "coach_notes")) == 1      # parti : il garde ses notes
    assert len(visible(seeded, "coachA", "coach_notes")) == 1       # plus celles du pilote parti
    assert visible(seeded, "coachB", "coach_notes") == set()


def test_structure_visible_only_to_members(seeded):
    _flag(seeded, True)
    assert visible(seeded, "p1", "structures", "name") == {"Ecole A"}
    assert visible(seeded, "outsider", "structures", "name") == set()


# ─────────────────────────────────────────────────────────────── retour arrière

def test_down_migration_keeps_pilot_sessions(seeded):
    with seeded.cursor() as c:
        c.execute("SELECT count(*) FROM public.analyses")
        before = c.fetchone()[0]
        for m in reversed(LATER):
            c.execute(m.with_name(m.name.replace(".sql", ".down.sql")).read_text())
        c.execute(DOWN.read_text())
        c.execute("SELECT count(*) FROM public.analyses")
        assert c.fetchone()[0] == before
        c.execute("SELECT to_regclass('public.structures')")
        assert c.fetchone()[0] is None
    assert visible(seeded, "coachA") == {"coachA_own"}
    # Et la migration se réapplique proprement.
    with seeded.cursor() as c:
        c.execute(MIGRATION.read_text())
