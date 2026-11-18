"""
Espace Team (écoles, clubs, coachs) — droits et niveau d'accès.

Un seul interrupteur : la ligne `team_space` de `public.app_flags` (coupée
par défaut). Coupé, rien ne change pour personne : ni accès coach (la RLS le
vérifie aussi), ni accès Racer accordé par une structure.
Coupure d'urgence côté API, sans toucher à la base : TEAM_SPACE_FORCE_OFF=1.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_FLAG_TTL_S = 60.0
_flag_cache: Dict[str, Any] = {"value": False, "at": 0.0}


def _client():
    from src.core.subscription_service import _get_supabase
    return _get_supabase()


def team_space_enabled(client: Any = None) -> bool:
    """L'interrupteur, lu dans la base et gardé une minute."""
    if os.getenv("TEAM_SPACE_FORCE_OFF", "").strip() in ("1", "true", "yes"):
        return False
    now = time.monotonic()
    if client is None and now - _flag_cache["at"] < _FLAG_TTL_S:
        return bool(_flag_cache["value"])
    sb = client or _client()
    value = False
    if sb is not None:
        try:
            res = sb.table("app_flags").select("enabled").eq("key", "team_space").limit(1).execute()
            value = bool(res.data and res.data[0].get("enabled"))
        except Exception as exc:  # table absente (migration non appliquée) : coupé
            logger.info("team_space: interrupteur illisible (%s), considéré coupé", exc)
            value = False
    if client is None:
        _flag_cache.update(value=value, at=now)
    return value


def _parse_dt(v: Any) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def structure_is_live(s: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    """Même règle que la fonction SQL public.structure_is_live."""
    now = now or datetime.now(timezone.utc)
    status = s.get("status")
    if status == "essai":
        until = _parse_dt(s.get("trial_until"))
        return bool(until and until > now)
    if status == "active":
        until = _parse_dt(s.get("contract_until"))
        return until is None or until > now
    return False


def active_memberships(user_id: str, client: Any = None) -> List[Dict[str, Any]]:
    """Adhésions actives de l'utilisateur dans des structures vivantes."""
    sb = client or _client()
    if sb is None or not user_id:
        return []
    try:
        res = (
            sb.table("structure_members")
            .select("structure_id, role, status, joined_at, structures(id, name, kind, status, trial_until, contract_until)")
            .eq("user_id", user_id)
            .eq("status", "actif")
            .execute()
        )
    except Exception as exc:
        logger.info("team_space: adhésions illisibles (%s)", exc)
        return []
    out = []
    for row in res.data or []:
        s = row.get("structures") or {}
        if s and structure_is_live(s):
            out.append({**row, "structure": s})
    return out


def structure_tier(user_id: str, client: Any = None) -> Optional[str]:
    """
    Accès accordé par une structure : « team » pour un coach, « racer » pour
    un pilote membre. None si l'interrupteur est coupé ou sans adhésion active.
    """
    if not user_id or not team_space_enabled(client):
        return None
    roles = {m.get("role") for m in active_memberships(user_id, client)}
    if "coach" in roles:
        return "team"
    if "pilote" in roles:
        return "racer"
    return None
