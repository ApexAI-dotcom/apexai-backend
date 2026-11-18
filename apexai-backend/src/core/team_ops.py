"""
Espace Team — règles métier (demandes, structures, adhésions, équipe).

Les règles vivent ici, la base derrière une petite interface (`TeamStore`) :
les routes restent minces et les tests tournent sans Supabase.

Rappels de conception (CONCEPTION_TEAM_MAILS_COLLECTE.md, 18/11) :
- une structure est créée par l'admin après le devis (essai 4 semaines par
  défaut, limites fixées au devis : NULL = pas de limite) ;
- un pilote rejoint par code, avec son ACCORD explicite ; pour un mineur,
  l'école certifie l'accord parental (case du coach, datée, nominative) ;
- le pilote garde tout en partant, et reçoit un mois Racer offert ;
- le coach lit (RLS) ; toute écriture passe par ici.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Protocol

from src.core.team_service import structure_is_live, _parse_dt

CONSENT_VERSION = "2026-11-18"
DEFAULT_TRIAL_WEEKS = 4
FAREWELL_DAYS = 30
INACTIVE_DAYS = 21
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans 0/O ni 1/I
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TIER_RANK = {"visitor": 0, "rookie": 1, "racer": 2, "team": 3}


class TeamError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_code(length: int = 8) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


class TeamStore(Protocol):
    def insert(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]: ...
    def update(self, table: str, match: Dict[str, Any], fields: Dict[str, Any]) -> None: ...
    def select(self, table: str, match: Optional[Dict[str, Any]] = None, columns: str = "*",
               order: Optional[str] = None, desc: bool = False, limit: Optional[int] = None) -> List[Dict[str, Any]]: ...
    def select_in(self, table: str, column: str, values: Iterable[Any], columns: str = "*",
                  since: Optional[str] = None) -> List[Dict[str, Any]]: ...
    def delete(self, table: str, match: Dict[str, Any]) -> None: ...
    def user_email(self, user_id: str) -> Optional[str]: ...


def _one(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return rows[0] if rows else None


def _clean(v: Any, n: int) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s[:n] if s else None


# ─────────────────────────────────────────────────────────── E1 · demandes

def create_contact_request(store: TeamStore, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
    name = _clean(payload.get("name"), 120)
    email = _clean(payload.get("email"), 254)
    if not name:
        raise TeamError(400, "Indique ton nom.")
    if not email or not _EMAIL_RE.match(email):
        raise TeamError(400, "Indique un email valide pour qu'on te réponde.")
    kind = payload.get("kind") if payload.get("kind") in ("ecole", "club", "coach", "autre") else "autre"
    # Une même adresse ne peut pas inonder la boîte : 3 demandes par 24 h.
    cutoff = _now() - timedelta(hours=24)
    recent = [r for r in store.select("contact_requests", {"email": email.lower()}, "id, created_at")
              if (_parse_dt(r.get("created_at")) or _now()) >= cutoff]
    if len(recent) >= 3:
        raise TeamError(429, "Ta demande est bien arrivée. On revient vers toi très vite.")
    row = {
        "name": name,
        "email": email.lower(),
        "phone": _clean(payload.get("phone"), 40),
        "structure_name": _clean(payload.get("structure_name"), 160),
        "kind": kind,
        "pilots_estimate": _clean(payload.get("pilots_estimate"), 40),
        "message": _clean(payload.get("message"), 4000),
        "user_id": user_id,
    }
    return store.insert("contact_requests", row)


def update_contact_request(store: TeamStore, request_id: str, status: Optional[str], note: Optional[str]) -> None:
    fields: Dict[str, Any] = {"updated_at": _now().isoformat()}
    if status is not None:
        if status not in ("nouvelle", "en_discussion", "signee", "sans_suite"):
            raise TeamError(400, "Statut inconnu.")
        fields["status"] = status
    if note is not None:
        fields["admin_note"] = _clean(note, 4000)
    store.update("contact_requests", {"id": request_id}, fields)


# ─────────────────────────────────────────────────────────── E2 · structures

def admin_create_structure(store: TeamStore, admin_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    name = _clean(payload.get("name"), 160)
    if not name:
        raise TeamError(400, "Donne un nom à la structure.")
    kind = payload.get("kind") if payload.get("kind") in ("ecole", "club", "coach") else "ecole"
    weeks = payload.get("trial_weeks", DEFAULT_TRIAL_WEEKS)
    try:
        weeks = int(weeks)
    except (TypeError, ValueError):
        raise TeamError(400, "Durée d'essai invalide.")
    if not 1 <= weeks <= 52:
        raise TeamError(400, "L'essai dure de 1 à 52 semaines.")
    limits = {}
    for key in ("max_pilots", "max_coaches", "max_karts"):
        v = payload.get(key)
        if v in (None, "", 0):
            limits[key] = None
        else:
            try:
                limits[key] = max(1, int(v))
            except (TypeError, ValueError):
                raise TeamError(400, "Limite invalide.")
    coach_email = _clean(payload.get("coach_email"), 254)
    if coach_email and not _EMAIL_RE.match(coach_email):
        raise TeamError(400, "Email du coach invalide.")
    structure = store.insert("structures", {
        "name": name,
        "kind": kind,
        "status": "essai",
        "trial_until": (_now() + timedelta(weeks=weeks)).isoformat(),
        "created_by": admin_id,
        "contact_request_id": payload.get("contact_request_id") or None,
        **limits,
    })
    invite = store.insert("structure_invites", {
        "code": new_code(12),
        "structure_id": structure["id"],
        "role": "coach",
        "email": coach_email.lower() if coach_email else None,
        "created_by": admin_id,
        "expires_at": (_now() + timedelta(days=30)).isoformat(),
        "max_uses": 1,
    })
    if payload.get("contact_request_id"):
        update_contact_request(store, payload["contact_request_id"], "signee", None)
    return {"structure": structure, "coach_invite": invite}


def admin_update_structure(store: TeamStore, structure_id: str, payload: Dict[str, Any]) -> None:
    fields: Dict[str, Any] = {"updated_at": _now().isoformat()}
    if "status" in payload:
        if payload["status"] not in ("essai", "active", "suspendue", "terminee"):
            raise TeamError(400, "Statut inconnu.")
        fields["status"] = payload["status"]
    for key in ("trial_until", "contract_until"):
        if key in payload:
            v = payload[key]
            if v and not _parse_dt(v):
                raise TeamError(400, "Date invalide.")
            fields[key] = v or None
    for key in ("max_pilots", "max_coaches", "max_karts"):
        if key in payload:
            v = payload[key]
            fields[key] = None if v in (None, "", 0) else max(1, int(v))
    if "name" in payload:
        fields["name"] = _clean(payload["name"], 160) or None
        if not fields["name"]:
            raise TeamError(400, "Nom vide.")
    if "notes_admin" in payload:
        fields["notes_admin"] = _clean(payload["notes_admin"], 4000)
    store.update("structures", {"id": structure_id}, fields)


def _get_structure(store: TeamStore, structure_id: str) -> Dict[str, Any]:
    s = _one(store.select("structures", {"id": structure_id}))
    if not s:
        raise TeamError(404, "Structure introuvable.")
    return s


def _member(store: TeamStore, structure_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    return _one(store.select("structure_members", {"structure_id": structure_id, "user_id": user_id}))


def require_coach(store: TeamStore, user_id: str, structure_id: str) -> Dict[str, Any]:
    s = _get_structure(store, structure_id)
    m = _member(store, structure_id, user_id)
    if not m or m.get("role") != "coach" or m.get("status") != "actif":
        raise TeamError(403, "Réservé aux coachs de cette structure.")
    if not structure_is_live(s):
        raise TeamError(403, "L'essai ou le contrat de cette structure est terminé.")
    return s


def _count_active(store: TeamStore, structure_id: str, role: str) -> int:
    return len(store.select("structure_members", {"structure_id": structure_id, "role": role, "status": "actif"}, "user_id"))


def create_pilot_invite(store: TeamStore, coach_id: str, structure_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    require_coach(store, coach_id, structure_id)
    days = payload.get("expires_days", 30)
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 30
    max_uses = payload.get("max_uses")
    return store.insert("structure_invites", {
        "code": new_code(8),
        "structure_id": structure_id,
        "role": "pilote",
        "created_by": coach_id,
        "expires_at": (_now() + timedelta(days=max(1, min(days, 365)))).isoformat(),
        "max_uses": int(max_uses) if max_uses else None,
        "guardian_certified": bool(payload.get("guardian_certified")),
    })


def _usable_invite(store: TeamStore, code: str) -> Dict[str, Any]:
    code = (code or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{6,32}", code):
        raise TeamError(404, "Ce code n'existe pas.")
    inv = _one(store.select("structure_invites", {"code": code}))
    if not inv or inv.get("revoked"):
        raise TeamError(404, "Ce code n'existe pas.")
    exp = _parse_dt(inv.get("expires_at"))
    if exp and exp <= _now():
        raise TeamError(410, "Ce code a expiré. Demande-en un nouveau à ton coach.")
    if inv.get("max_uses") and int(inv.get("uses") or 0) >= int(inv["max_uses"]):
        raise TeamError(410, "Ce code a déjà servi. Demande-en un nouveau à ton coach.")
    return inv


def invite_info(store: TeamStore, code: str) -> Dict[str, Any]:
    """Ce qu'on montre AVANT d'accepter : le nom de la structure et le rôle."""
    inv = _usable_invite(store, code)
    s = _get_structure(store, inv["structure_id"])
    if not structure_is_live(s):
        raise TeamError(410, "Cette structure n'accueille plus de nouveaux membres.")
    return {"structure": {"id": s["id"], "name": s["name"], "kind": s["kind"]}, "role": inv["role"],
            "consent_version": CONSENT_VERSION}


def join(store: TeamStore, user_id: str, code: str, consent: bool) -> Dict[str, Any]:
    inv = _usable_invite(store, code)
    s = _get_structure(store, inv["structure_id"])
    if not structure_is_live(s):
        raise TeamError(410, "Cette structure n'accueille plus de nouveaux membres.")
    role = inv["role"]
    if role == "pilote" and not consent:
        raise TeamError(400, "Ton accord est nécessaire pour rejoindre la structure.")
    if role == "coach" and inv.get("email"):
        email = (store.user_email(user_id) or "").lower()
        if email != inv["email"].lower():
            raise TeamError(403, "Cette invitation coach est réservée à une autre adresse email.")
    existing = _member(store, s["id"], user_id)
    if existing and existing.get("status") == "actif":
        if existing.get("role") == role or existing.get("role") == "coach":
            return {"structure_id": s["id"], "role": existing["role"], "already": True}
    limit_key = "max_pilots" if role == "pilote" else "max_coaches"
    if s.get(limit_key) and _count_active(store, s["id"], role) >= int(s[limit_key]):
        raise TeamError(409, "La structure a atteint son nombre de places. Préviens ton coach.")
    now = _now().isoformat()
    row = {
        "structure_id": s["id"],
        "user_id": user_id,
        "role": role,
        "status": "actif",
        "consent_at": now if role == "pilote" else None,
        "consent_version": CONSENT_VERSION if role == "pilote" else None,
        "guardian_certified_by": inv.get("created_by") if inv.get("guardian_certified") else None,
        "guardian_certified_at": now if inv.get("guardian_certified") else None,
        "joined_at": now,
        "left_at": None,
    }
    if existing:
        store.update("structure_members", {"structure_id": s["id"], "user_id": user_id},
                     {k: v for k, v in row.items() if k not in ("structure_id", "user_id")})
    else:
        store.insert("structure_members", row)
    store.update("structure_invites", {"code": inv["code"]}, {"uses": int(inv.get("uses") or 0) + 1})
    return {"structure_id": s["id"], "role": role, "already": False}


def _grant_farewell_month(store: TeamStore, user_id: str) -> Optional[str]:
    """Un mois Racer offert au départ, sauf abonné Racer ou Team payant."""
    prof = _one(store.select("profiles", {"id": user_id}, "subscription_tier, trial_tier, trial_until"))
    if not prof:
        return None
    paid = (prof.get("subscription_tier") or "rookie").lower()
    if _TIER_RANK.get(paid, 0) >= _TIER_RANK["racer"]:
        return None
    until = _now() + timedelta(days=FAREWELL_DAYS)
    cur = _parse_dt(prof.get("trial_until"))
    if cur and cur > until and _TIER_RANK.get((prof.get("trial_tier") or "").lower(), 0) >= _TIER_RANK["racer"]:
        return cur.isoformat()
    store.update("profiles", {"id": user_id}, {"trial_tier": "racer", "trial_until": until.isoformat()})
    return until.isoformat()


def leave(store: TeamStore, user_id: str, structure_id: str) -> Dict[str, Any]:
    m = _member(store, structure_id, user_id)
    if not m or m.get("status") != "actif":
        raise TeamError(404, "Tu n'es pas membre de cette structure.")
    store.update("structure_members", {"structure_id": structure_id, "user_id": user_id},
                 {"status": "parti", "left_at": _now().isoformat()})
    gift = _grant_farewell_month(store, user_id) if m.get("role") == "pilote" else None
    return {"left": True, "racer_until": gift}


def remove_pilot(store: TeamStore, coach_id: str, structure_id: str, pilot_id: str) -> Dict[str, Any]:
    require_coach(store, coach_id, structure_id)
    m = _member(store, structure_id, pilot_id)
    if not m or m.get("role") != "pilote" or m.get("status") != "actif":
        raise TeamError(404, "Ce pilote n'est pas membre actif de ta structure.")
    store.update("structure_members", {"structure_id": structure_id, "user_id": pilot_id},
                 {"status": "retire", "left_at": _now().isoformat()})
    return {"removed": True, "racer_until": _grant_farewell_month(store, pilot_id)}


def share_analysis(store: TeamStore, user_id: str, structure_id: str, analysis_id: str, share: bool = True) -> None:
    m = _member(store, structure_id, user_id)
    if not m or m.get("role") != "pilote" or m.get("status") != "actif":
        raise TeamError(403, "Tu n'es pas membre de cette structure.")
    a = _one(store.select("analyses", {"id": analysis_id}, "id, user_id"))
    if not a or a.get("user_id") != user_id:
        raise TeamError(404, "Séance introuvable.")
    if share:
        if not store.select("shared_analyses", {"structure_id": structure_id, "analysis_id": analysis_id}):
            store.insert("shared_analyses", {"structure_id": structure_id, "analysis_id": analysis_id, "pilot_id": user_id})
    else:
        store.delete("shared_analyses", {"structure_id": structure_id, "analysis_id": analysis_id, "pilot_id": user_id})


# ─────────────────────────────────────────────────────────── E3 · vue équipe

def my_memberships(store: TeamStore, user_id: str) -> List[Dict[str, Any]]:
    out = []
    for m in store.select("structure_members", {"user_id": user_id, "status": "actif"}):
        s = _one(store.select("structures", {"id": m["structure_id"]}))
        if not s:
            continue
        out.append({
            "structure": {"id": s["id"], "name": s["name"], "kind": s["kind"], "status": s["status"],
                          "trial_until": s.get("trial_until"), "live": structure_is_live(s)},
            "role": m["role"],
            "joined_at": m.get("joined_at"),
        })
    return out


def _display_name(profile: Optional[Dict[str, Any]]) -> str:
    """Le nom du COMPTE (jamais celui d'un fichier de session), au prénom."""
    full = (profile or {}).get("full_name") or ""
    first = full.strip().split(" ")[0] if full.strip() else ""
    return first or "Pilote"


def team_overview(store: TeamStore, coach_id: str, structure_id: str) -> Dict[str, Any]:
    s = require_coach(store, coach_id, structure_id)
    members = store.select("structure_members", {"structure_id": structure_id, "status": "actif"})
    pilots = [m for m in members if m.get("role") == "pilote"]
    ids = [m["user_id"] for m in pilots]
    profiles = {p["id"]: p for p in store.select_in("profiles", "id", ids, "id, full_name")} if ids else {}
    shared = {r["analysis_id"] for r in store.select("shared_analyses", {"structure_id": structure_id}, "analysis_id")}
    analyses = store.select_in("analyses", "user_id", ids, "id, user_id, created_at, circuit_name, best_lap_time") if ids else []
    joined = {m["user_id"]: _parse_dt(m.get("joined_at")) for m in pilots}
    visible = [a for a in analyses
               if a["id"] in shared or ((_parse_dt(a.get("created_at")) or _now()) >= (joined.get(a["user_id"]) or _now()))]
    now = _now()
    out_pilots, alerts, ranking = [], [], {}
    for m in pilots:
        uid = m["user_id"]
        mine = sorted((a for a in visible if a["user_id"] == uid),
                      key=lambda a: _parse_dt(a.get("created_at")) or now, reverse=True)
        last = mine[0] if mine else None
        name = _display_name(profiles.get(uid))
        trend = _trend(mine, now)
        last_at = _parse_dt(last.get("created_at")) if last else None
        inactive = (last_at is None and (now - (joined.get(uid) or now)).days >= INACTIVE_DAYS) or \
                   (last_at is not None and (now - last_at).days >= INACTIVE_DAYS)
        if inactive:
            days = (now - (last_at or joined.get(uid) or now)).days
            alerts.append({"kind": "inactif", "pilot_id": uid, "text": f"{name} n'a pas roulé depuis {days // 7} semaines"})
        for a in mine:
            c, t = a.get("circuit_name"), a.get("best_lap_time")
            if c and t and t > 0:
                best = ranking.setdefault(c, {})
                if uid not in best or t < best[uid]:
                    best[uid] = t
        out_pilots.append({
            "user_id": uid,
            "name": name,
            "joined_at": m.get("joined_at"),
            "sessions": len(mine),
            "last_session": {"id": last["id"], "date": last.get("created_at"), "circuit": last.get("circuit_name"),
                             "best_lap": last.get("best_lap_time")} if last else None,
            "trend_30d": trend,
            "inactive": inactive,
        })
    names = {p["user_id"]: p["name"] for p in out_pilots}
    rankings = [
        {"circuit": c, "rows": [{"user_id": u, "name": names.get(u, "Pilote"), "best_lap": t}
                                for u, t in sorted(rows.items(), key=lambda kv: kv[1])]}
        for c, rows in sorted(ranking.items(), key=lambda kv: -len(kv[1]))
    ]
    return {
        "structure": {"id": s["id"], "name": s["name"], "kind": s["kind"], "status": s["status"],
                      "trial_until": s.get("trial_until"), "max_pilots": s.get("max_pilots")},
        "coaches": len([m for m in members if m.get("role") == "coach"]),
        "pilots": out_pilots,
        "alerts": alerts,
        "rankings": rankings,
    }


def _trend(sessions: List[Dict[str, Any]], now: datetime) -> Optional[float]:
    """Progression sur 30 jours : meilleur tour récent − meilleur tour d'avant, même circuit."""
    cutoff = now - timedelta(days=30)
    by_circuit: Dict[str, Dict[str, List[float]]] = {}
    for a in sessions:
        c, t, d = a.get("circuit_name"), a.get("best_lap_time"), _parse_dt(a.get("created_at"))
        if not c or not t or t <= 0 or not d:
            continue
        bucket = by_circuit.setdefault(c, {"recent": [], "before": []})
        bucket["recent" if d >= cutoff else "before"].append(float(t))
    deltas = [min(b["recent"]) - min(b["before"]) for b in by_circuit.values() if b["recent"] and b["before"]]
    if not deltas:
        return None
    return round(sum(deltas) / len(deltas), 3)


def pilot_sessions(store: TeamStore, coach_id: str, structure_id: str, pilot_id: str) -> Dict[str, Any]:
    """Liste des séances d'un pilote visibles par le coach (même règle que la RLS)."""
    require_coach(store, coach_id, structure_id)
    m = _member(store, structure_id, pilot_id)
    if not m or m.get("role") != "pilote" or m.get("status") != "actif":
        raise TeamError(404, "Ce pilote n'est pas membre actif de ta structure.")
    joined = _parse_dt(m.get("joined_at")) or _now()
    shared = {r["analysis_id"] for r in store.select("shared_analyses", {"structure_id": structure_id, "pilot_id": pilot_id}, "analysis_id")}
    rows = store.select("analyses", {"user_id": pilot_id},
                        "id, created_at, circuit_name, session_name, best_lap_time, score, uploaded_by",
                        order="created_at", desc=True, limit=500)
    out = [r for r in rows if r["id"] in shared or (_parse_dt(r.get("created_at")) or _now()) >= joined]
    prof = _one(store.select("profiles", {"id": pilot_id}, "id, full_name"))
    return {"pilot": {"user_id": pilot_id, "name": _display_name(prof), "joined_at": m.get("joined_at")},
            "sessions": [{**r, "shared": r["id"] in shared} for r in out]}


# ─────────────────────────────────────────────────────────── admin

def admin_overview(store: TeamStore) -> Dict[str, Any]:
    structures = store.select("structures", None, order="created_at", desc=True)
    requests = store.select("contact_requests", None, order="created_at", desc=True, limit=200)
    out = []
    month_ago = (_now() - timedelta(days=30)).isoformat()
    for s in structures:
        members = store.select("structure_members", {"structure_id": s["id"], "status": "actif"}, "user_id, role")
        pilot_ids = [m["user_id"] for m in members if m["role"] == "pilote"]
        recent = store.select_in("analyses", "user_id", pilot_ids, "id", since=month_ago) if pilot_ids else []
        invites = store.select("structure_invites", {"structure_id": s["id"], "role": "coach", "revoked": False}, "code, email, uses, max_uses, expires_at")
        out.append({**s, "live": structure_is_live(s),
                    "coaches": len([m for m in members if m["role"] == "coach"]),
                    "pilots": len(pilot_ids), "analyses_30d": len(recent),
                    "coach_invites": [i for i in invites if not i.get("max_uses") or int(i.get("uses") or 0) < int(i["max_uses"])]})
    return {"structures": out, "requests": requests}


# ─────────────────────────────────────────────────────────── stockage Supabase

class SupabaseTeamStore:
    """Implémentation de TeamStore sur le client Supabase (clé de service)."""

    def __init__(self, client: Any):
        self.sb = client

    def insert(self, table, row):
        res = self.sb.table(table).insert(row).execute()
        return (res.data or [row])[0]

    def update(self, table, match, fields):
        q = self.sb.table(table).update(fields)
        for k, v in match.items():
            q = q.eq(k, v)
        q.execute()

    def select(self, table, match=None, columns="*", order=None, desc=False, limit=None):
        q = self.sb.table(table).select(columns)
        for k, v in (match or {}).items():
            q = q.eq(k, v)
        if order:
            q = q.order(order, desc=desc)
        if limit:
            q = q.limit(limit)
        return q.execute().data or []

    def select_in(self, table, column, values, columns="*", since=None):
        values = list(values)
        if not values:
            return []
        q = self.sb.table(table).select(columns).in_(column, values)
        if since:
            q = q.gte("created_at", since)
        return q.execute().data or []

    def delete(self, table, match):
        q = self.sb.table(table).delete()
        for k, v in match.items():
            q = q.eq(k, v)
        q.execute()

    def user_email(self, user_id):
        try:
            u = self.sb.auth.admin.get_user_by_id(user_id)
            return getattr(getattr(u, "user", None), "email", None)
        except Exception:
            return None
