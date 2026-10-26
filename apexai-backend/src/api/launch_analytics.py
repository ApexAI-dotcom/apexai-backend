#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Suivi de lancement pour le back-office.

Transforme les évènements de navigation (page_events), les comptes et les
analyses en indicateurs lisibles : visiteurs réels (un visiteur = un
navigateur, quelle que soit la quantité de pages vues), visites (coupées après
30 minutes sans activité), provenance, parcours page par page, inscrits et ce
qu'ils ont fait. L'équipe (comptes du back-office et leurs navigateurs) est
exclue de tous les chiffres.

Fonctions pures, sans accès réseau : testées dans tests/test_launch_analytics.py.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
VISIT_GAP = timedelta(minutes=30)
ONLINE_WINDOW = timedelta(minutes=5)

SOURCE_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("Instagram", ("instagram", "ig")),
    ("TikTok", ("tiktok",)),
    ("Facebook", ("facebook", "fb", "messenger")),
    ("WhatsApp", ("whatsapp", "wa.me")),
    ("Google", ("google",)),
    ("YouTube", ("youtube", "youtu.be")),
    ("Snapchat", ("snapchat",)),
    ("LinkedIn", ("linkedin", "lnkd")),
    ("Bing", ("bing",)),
]
OWN_HOSTS = ("apexai.racing", "vercel.app", "localhost")


def parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Fractions de seconde à 5 chiffres renvoyées par PostgREST
        head, _, tail = s.partition(".")
        frac, sign, tz = tail[:6], "", ""
        for sep in ("+", "-"):
            if sep in tail:
                frac, tz = tail.split(sep, 1)
                sign = sep
                break
        dt = datetime.fromisoformat(f"{head}.{frac.ljust(6, '0')[:6]}{sign}{tz}" if frac else head)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def classify_source(referrer: Optional[str], utm_source: Optional[str] = None) -> str:
    """Provenance lisible : réseau social, moteur de recherche, site, ou accès direct."""
    probe = (utm_source or "").strip().lower()
    host = ""
    if referrer:
        try:
            host = (urlparse(referrer).hostname or "").lower()
        except ValueError:
            host = ""
    for label, keys in SOURCE_RULES:
        if any(k == probe or (len(k) > 2 and k in probe) for k in keys if probe):
            return label
        if host and any(k in host for k in keys if len(k) > 2 or "." in k):
            return label
    if probe:
        return probe[:40]
    if not host or any(h in host for h in OWN_HOSTS):
        return "Accès direct"
    return host.removeprefix("www.")[:60]


def _day(dt: datetime) -> str:
    return dt.astimezone(PARIS).strftime("%Y-%m-%d")


def short_visitor(session_id: Optional[str]) -> str:
    return f"Visiteur {((session_id or 'anon').replace('-', '')[:4]).upper()}"


def segment_visits(events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Regroupe les évènements en visites : identifiant de visite s'il existe,
    sinon même navigateur sans pause de plus de 30 minutes."""
    by_visitor: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
        by_visitor[e.get("session_id") or "anon"].append(e)
    visits: Dict[str, List[Dict[str, Any]]] = {}
    for sid, evs in by_visitor.items():
        evs.sort(key=lambda e: e["_ts"])
        n, last_ts, current = 0, None, None
        for e in evs:
            if e.get("visit_id"):
                key = f"{sid}:{e['visit_id']}"
            else:
                if current is None or last_ts is None or e["_ts"] - last_ts > VISIT_GAP:
                    n += 1
                    current = f"{sid}:v{n}"
                key = current
            visits.setdefault(key, []).append(e)
            last_ts = e["_ts"]
    return visits


def build_launch_report(
    events: Iterable[Dict[str, Any]],
    users: List[Dict[str, Any]],
    analyses: List[Dict[str, Any]],
    team_user_ids: Iterable[str],
    now: datetime,
    days: int = 14,
) -> Dict[str, Any]:
    team = {str(u) for u in team_user_ids if u}
    evs: List[Dict[str, Any]] = []
    for e in events:
        ts = parse_ts(e.get("created_at"))
        if ts is None:
            continue
        e = dict(e)
        e["_ts"] = ts
        evs.append(e)

    # Navigateur -> compte (le dernier compte vu sur ce navigateur)
    visitor_user: Dict[str, str] = {}
    for e in sorted(evs, key=lambda x: x["_ts"]):
        if e.get("user_id") and e.get("session_id"):
            visitor_user[e["session_id"]] = str(e["user_id"])
    team_visitors = {sid for sid, uid in visitor_user.items() if uid in team}
    evs = [e for e in evs if str(e.get("user_id") or "") not in team and e.get("session_id") not in team_visitors]
    users = [u for u in users if str(u.get("user_id")) not in team]
    user_by_id = {str(u["user_id"]): u for u in users}

    start = now - timedelta(days=days)
    prev_start = start - timedelta(days=days)

    visits = segment_visits(evs)
    visit_rows: List[Dict[str, Any]] = []
    for key, vevs in visits.items():
        vevs.sort(key=lambda e: e["_ts"])
        sid = vevs[0].get("session_id")
        uid = next((str(e["user_id"]) for e in vevs if e.get("user_id")), None) or visitor_user.get(sid or "")
        first = vevs[0]
        views = [e for e in vevs if e.get("event_type") == "view"]
        leaves = {}
        for e in vevs:
            if e.get("event_type") == "leave" and e.get("duration_ms"):
                leaves.setdefault(e.get("path"), []).append(int(e["duration_ms"]))
        pages = []
        for v in views:
            secs = None
            if leaves.get(v.get("path")):
                secs = round(leaves[v["path"]].pop(0) / 1000)
            pages.append({"path": v.get("path"), "at": v["_ts"].isoformat(), "seconds": secs})
        if not views:
            continue
        end = vevs[-1]["_ts"]
        visit_rows.append({
            "key": key,
            "visitor": sid,
            "user_id": uid,
            "started": views[0]["_ts"],
            "ended": max(end, views[-1]["_ts"]),
            "pages": pages,
            "source": classify_source(first.get("referrer"), first.get("utm_source")),
            "campaign": first.get("utm_campaign"),
            "device": next((e.get("device") for e in vevs if e.get("device")), None),
        })
    visit_rows.sort(key=lambda v: v["started"])

    # Première provenance de chaque navigateur, puis de chaque compte
    visitor_first: Dict[str, Dict[str, Any]] = {}
    for v in visit_rows:
        visitor_first.setdefault(v["visitor"], v)
    user_source: Dict[str, str] = {}
    for sid, v in visitor_first.items():
        uid = visitor_user.get(sid or "")
        if uid and (uid not in user_source):
            user_source[uid] = v["source"]

    def in_window(dt: Optional[datetime], a: datetime, b: datetime) -> bool:
        return dt is not None and a <= dt < b

    def period(a: datetime, b: datetime) -> Dict[str, Any]:
        pv = [v for v in visit_rows if in_window(v["started"], a, b)]
        visitors = {v["visitor"] for v in pv}
        new_visitors = {sid for sid in visitors if in_window(visitor_first[sid]["started"], a, b)}
        signups = [u for u in users if in_window(parse_ts(u.get("created_at")), a, b)]
        activated = [u for u in signups if (u.get("analyses") or 0) > 0]
        an = [x for x in analyses if in_window(parse_ts(x.get("created_at")), a, b) and str(x.get("user_id")) not in team]
        durations = [(v["ended"] - v["started"]).total_seconds() for v in pv if len(v["pages"]) > 1]
        return {
            "visitors": len(visitors),
            "new_visitors": len(new_visitors),
            "visits": len(pv),
            "signups": len(signups),
            "activated": len(activated),
            "analyses": len(an),
            "pages_per_visit": round(sum(len(v["pages"]) for v in pv) / len(pv), 1) if pv else None,
            "avg_visit_seconds": round(sum(durations) / len(durations)) if durations else None,
        }

    cur = period(start, now + timedelta(seconds=1))
    prev = period(prev_start, start)

    paying = [u for u in users if (u.get("tier") or "").lower() in ("racer", "team") and (u.get("subscription_status") or "active") in ("active", "trialing")]
    trials = [u for u in users if parse_ts(u.get("trial_until")) and parse_ts(u.get("trial_until")) > now]
    online = {e.get("session_id") for e in evs if now - e["_ts"] <= ONLINE_WINDOW}

    # Série quotidienne (heure de Paris)
    daily: Dict[str, Dict[str, Any]] = {}
    for i in range(days, -1, -1):
        d = _day(now - timedelta(days=i))
        daily[d] = {"date": d, "visitors": set(), "signups": 0, "analyses": 0}
    for v in visit_rows:
        d = _day(v["started"])
        if d in daily:
            daily[d]["visitors"].add(v["visitor"])
    for u in users:
        ts = parse_ts(u.get("created_at"))
        if ts and _day(ts) in daily:
            daily[_day(ts)]["signups"] += 1
    for x in analyses:
        ts = parse_ts(x.get("created_at"))
        if ts and _day(ts) in daily and str(x.get("user_id")) not in team:
            daily[_day(ts)]["analyses"] += 1
    daily_rows = [{**d, "visitors": len(d["visitors"])} for d in daily.values()]

    # Provenance des nouveaux visiteurs de la période, et inscrits qui en viennent
    sources: Dict[str, Dict[str, Any]] = {}
    for sid, v in visitor_first.items():
        if not in_window(v["started"], start, now + timedelta(seconds=1)):
            continue
        s = sources.setdefault(v["source"], {"source": v["source"], "visitors": 0, "signups": 0})
        s["visitors"] += 1
    for u in users:
        if in_window(parse_ts(u.get("created_at")), start, now + timedelta(seconds=1)):
            src = user_source.get(str(u["user_id"]), "Inconnue")
            s = sources.setdefault(src, {"source": src, "visitors": 0, "signups": 0})
            s["signups"] += 1
    source_rows = sorted(sources.values(), key=lambda s: (-s["visitors"], -s["signups"]))

    # Pages : nombre de visites qui l'ont vue, temps moyen
    page_stats: Dict[str, Dict[str, Any]] = {}
    for v in visit_rows:
        if not in_window(v["started"], start, now + timedelta(seconds=1)):
            continue
        seen = set()
        for p in v["pages"]:
            st = page_stats.setdefault(p["path"], {"path": p["path"], "visits": 0, "secs": []})
            if p["path"] not in seen:
                st["visits"] += 1
                seen.add(p["path"])
            if p["seconds"] is not None and p["seconds"] < 3600:
                st["secs"].append(p["seconds"])
    page_rows = sorted(
        ({"path": s["path"], "visits": s["visits"], "avg_seconds": round(sum(s["secs"]) / len(s["secs"])) if s["secs"] else None} for s in page_stats.values()),
        key=lambda s: -s["visits"],
    )[:15]

    devices: Dict[str, int] = defaultdict(int)
    for sid, v in visitor_first.items():
        if in_window(v["started"], start, now + timedelta(seconds=1)):
            devices[v["device"] or "inconnu"] += 1

    def who(uid: Optional[str], sid: Optional[str]) -> Dict[str, Any]:
        u = user_by_id.get(uid or "")
        if u:
            return {"user_id": uid, "name": u.get("full_name") or (u.get("email") or "").split("@")[0], "email": u.get("email")}
        return {"user_id": None, "name": short_visitor(sid), "email": None}

    recent = sorted(visit_rows, key=lambda v: v["started"], reverse=True)[:40]
    visit_out = [{
        "id": v["key"],
        **who(v["user_id"], v["visitor"]),
        "started_at": v["started"].isoformat(),
        "duration_s": round((v["ended"] - v["started"]).total_seconds()),
        "pages": v["pages"][:30],
        "source": v["source"],
        "campaign": v["campaign"],
        "device": v["device"],
        "online": v["visitor"] in online,
    } for v in recent]

    last_seen: Dict[str, datetime] = {}
    visits_count: Dict[str, int] = defaultdict(int)
    for v in visit_rows:
        if v["user_id"]:
            visits_count[v["user_id"]] += 1
            if v["ended"] > last_seen.get(v["user_id"], datetime.min.replace(tzinfo=timezone.utc)):
                last_seen[v["user_id"]] = v["ended"]
    user_rows = []
    for u in users:
        uid = str(u["user_id"])
        seen = [t for t in (last_seen.get(uid), parse_ts(u.get("last_sign_in_at")), parse_ts(u.get("last_analysis_at"))) if t]
        user_rows.append({
            "user_id": uid,
            "name": u.get("full_name"),
            "email": u.get("email"),
            "provider": u.get("provider"),
            "created_at": u.get("created_at"),
            "confirmed": u.get("confirmed"),
            "last_seen": max(seen).isoformat() if seen else None,
            "visits": visits_count.get(uid, 0),
            "analyses": u.get("analyses") or 0,
            "first_analysis_at": u.get("first_analysis_at"),
            "last_analysis_at": u.get("last_analysis_at"),
            "circuits": [c for c in (u.get("circuits") or []) if c][:6],
            "tier": (u.get("tier") or "rookie"),
            "trial_until": u.get("trial_until") if (parse_ts(u.get("trial_until")) and parse_ts(u.get("trial_until")) > now) else None,
            "source": user_source.get(uid),
            "devices": u.get("devices") or 0,
        })

    return {
        "window_days": days,
        "generated_at": now.isoformat(),
        "kpis": {"current": cur, "previous": prev, "paying": len(paying), "trials": len(trials), "online_now": len(online), "users_total": len(users)},
        "funnel": [
            {"step": "Nouveaux visiteurs", "value": cur["new_visitors"]},
            {"step": "Inscrits", "value": cur["signups"]},
            {"step": "Première analyse", "value": cur["activated"]},
            {"step": "Abonnés", "value": len([u for u in paying if in_window(parse_ts(u.get("created_at")), start, now + timedelta(seconds=1))])},
        ],
        "daily": daily_rows,
        "sources": source_rows[:12],
        "pages": page_rows,
        "devices": dict(devices),
        "visits": visit_out,
        "users": user_rows,
        "tracking_since": min((e["_ts"] for e in evs), default=now).isoformat(),
        "tracking_identified_since": min((e["_ts"] for e in evs if e.get("user_id")), default=None).isoformat() if any(e.get("user_id") for e in evs) else None,
    }
