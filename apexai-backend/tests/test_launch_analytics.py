from datetime import datetime, timedelta, timezone

from src.api.launch_analytics import build_launch_report, classify_source, segment_visits

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def ev(sid, minutes_ago, path="/", kind="view", **kw):
    return {"session_id": sid, "created_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(), "path": path, "event_type": kind, **kw}


def test_sources_are_readable():
    assert classify_source("https://l.instagram.com/?u=x") == "Instagram"
    assert classify_source(None, "tiktok") == "TikTok"
    assert classify_source("https://www.google.fr/") == "Google"
    assert classify_source("https://www.apexai.racing/upload") == "Accès direct"
    assert classify_source(None) == "Accès direct"
    assert classify_source("https://www.kartingmag.fr/article") == "kartingmag.fr"


def test_visits_split_after_30_minutes_of_inactivity():
    evs = [ev("a", 120), ev("a", 110, "/upload"), ev("a", 20), ev("a", 10, "/dashboard")]
    for e in evs:
        e["_ts"] = datetime.fromisoformat(e["created_at"])
    visits = segment_visits(evs)
    assert sorted(len(v) for v in visits.values()) == [2, 2]


def test_one_browser_changing_pages_is_one_visitor():
    events = [ev("a", 30 - i, f"/p{i}") for i in range(10)] + [ev("a", 25, "/p1", "leave", duration_ms=4000)]
    r = build_launch_report(events, [], [], [], NOW, 14)
    assert r["kpis"]["current"]["visitors"] == 1
    assert r["kpis"]["current"]["visits"] == 1
    assert len(r["visits"][0]["pages"]) == 10


def test_team_is_excluded_including_anonymous_visits_of_its_browser():
    team = "11111111-1111-1111-1111-111111111111"
    events = [ev("yanis", 300), ev("yanis", 200, user_id=team), ev("pilot", 50)]
    users = [{"user_id": team, "email": "y@x.fr", "created_at": (NOW - timedelta(days=90)).isoformat()}]
    r = build_launch_report(events, users, [], [team], NOW, 14)
    assert r["kpis"]["current"]["visitors"] == 1
    assert r["kpis"]["users_total"] == 0


def test_signup_is_attributed_to_the_first_source_of_its_browser():
    uid = "22222222-2222-2222-2222-222222222222"
    events = [
        ev("b", 600, referrer="https://l.instagram.com/"),
        ev("b", 100, "/upload", user_id=uid),
    ]
    users = [{"user_id": uid, "email": "camille@x.fr", "full_name": "Camille", "created_at": (NOW - timedelta(minutes=90)).isoformat(), "analyses": 1}]
    r = build_launch_report(events, users, [{"user_id": uid, "created_at": NOW.isoformat()}], [], NOW, 14)
    assert r["users"][0]["source"] == "Instagram"
    assert r["kpis"]["current"]["signups"] == 1
    assert r["kpis"]["current"]["activated"] == 1
    insta = next(s for s in r["sources"] if s["source"] == "Instagram")
    assert insta == {"source": "Instagram", "visitors": 1, "signups": 1}
    assert r["visits"][0]["name"] == "Camille"
