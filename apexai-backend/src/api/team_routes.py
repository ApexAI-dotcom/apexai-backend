"""
Espace Team (écoles, clubs, coachs) — routes de l'API.

- Public : demande « Contactez-nous » (offre Team sur devis), aperçu d'un code.
- Membre : rejoindre avec son accord, quitter, partager une ancienne séance.
- Coach : vue équipe, séances d'un pilote, codes pilotes, retrait d'un pilote.
- Admin : demandes et structures.

Interrupteur : app_flags('team_space'). Coupé, tout est fermé sauf la demande
de contact (l'offre Team sur devis existe même sans l'espace coach).
"""
from __future__ import annotations

import html
import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.core import team_ops
from src.core.team_ops import SupabaseTeamStore, TeamError
from src.core.team_service import team_space_enabled

from .admin_panel_routes import require_permission, supabase as admin_supabase
from .auth import get_current_user
from .rate_limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["team"])

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
TEAM_CONTACT_TO = os.getenv("TEAM_CONTACT_TO", "contact@apexai.racing")
EMAIL_FROM = os.getenv("EMAIL_FROM", "ApexAI <noreply@apexai.racing>")


def _store() -> SupabaseTeamStore:
    if admin_supabase is None:
        raise HTTPException(status_code=503, detail="Service indisponible.")
    return SupabaseTeamStore(admin_supabase)


def _require_enabled():
    if not team_space_enabled():
        raise HTTPException(status_code=404, detail="L'espace Team n'est pas encore ouvert.")


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except TeamError as e:
        raise HTTPException(status_code=e.status, detail=e.message)


# ─────────────────────────────────────────────── public : contact (E1)

class ContactIn(BaseModel):
    name: str = Field(max_length=120)
    email: str = Field(max_length=254)
    phone: Optional[str] = Field(default=None, max_length=40)
    structure_name: Optional[str] = Field(default=None, max_length=160)
    kind: Optional[str] = "ecole"
    pilots_estimate: Optional[str] = Field(default=None, max_length=40)
    message: Optional[str] = Field(default=None, max_length=4000)
    website: Optional[str] = None  # champ piège anti-robot : rempli = ignoré


def _notify_contact(row: Dict[str, Any]) -> None:
    """Prévient Yanis par mail (Resend), si la clé est configurée sur l'API."""
    if not RESEND_API_KEY:
        logger.info("team contact: RESEND_API_KEY absent, demande visible dans l'admin seulement")
        return
    e = {k: html.escape(str(row.get(k) or "—")) for k in ("name", "email", "phone", "structure_name", "kind", "pilots_estimate", "message")}
    body = (
        f"<h2 style='font-family:Arial'>Nouvelle demande Team</h2>"
        f"<p style='font-family:Arial'><b>{e['name']}</b> · {e['structure_name']} ({e['kind']}) · {e['pilots_estimate']} pilotes<br>"
        f"{e['email']} · {e['phone']}</p><p style='font-family:Arial;white-space:pre-line'>{e['message']}</p>"
        f"<p style='font-family:Arial'><a href='https://www.apexai.racing/admin?tab=team'>Ouvrir dans l'admin</a></p>"
    )
    try:
        httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": EMAIL_FROM, "to": [TEAM_CONTACT_TO], "reply_to": row.get("email"),
                  "subject": f"Demande Team : {row.get('structure_name') or row.get('name')}",
                  "html": body, "tags": [{"name": "category", "value": "team_contact"}]},
            timeout=8.0,
        )
    except Exception as exc:  # la demande est enregistrée : le mail est un plus
        logger.warning("team contact: mail non envoyé (%s)", exc)


@router.post("/api/team/contact")
@limiter.limit("5/hour")
async def team_contact(request: Request, payload: ContactIn):
    if payload.website:
        return {"ok": True}
    user_id = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            user_id = await get_current_user(auth[7:].strip())
        except Exception:
            user_id = None
    row = _run(team_ops.create_contact_request, _store(), payload.model_dump(), user_id)
    _notify_contact(row)
    return {"ok": True}


# ─────────────────────────────────────────────── membres (E2)

class JoinIn(BaseModel):
    code: str
    consent: bool = False


@router.get("/api/team/invite/{code}")
@limiter.limit("30/minute")
async def team_invite(request: Request, code: str):
    _require_enabled()
    return _run(team_ops.invite_info, _store(), code)


@router.post("/api/team/join")
@limiter.limit("10/minute")
async def team_join(request: Request, payload: JoinIn, current_user: str = Depends(get_current_user)):
    _require_enabled()
    return _run(team_ops.join, _store(), current_user, payload.code, payload.consent)


@router.get("/api/team/me")
async def team_me(current_user: str = Depends(get_current_user)):
    if not team_space_enabled():
        return {"enabled": False, "memberships": []}
    return {"enabled": True, "memberships": _run(team_ops.my_memberships, _store(), current_user)}


@router.post("/api/team/{structure_id}/leave")
async def team_leave(structure_id: str, current_user: str = Depends(get_current_user)):
    _require_enabled()
    return _run(team_ops.leave, _store(), current_user, structure_id)


class ShareIn(BaseModel):
    analysis_id: str
    share: bool = True


@router.post("/api/team/{structure_id}/share")
async def team_share(structure_id: str, payload: ShareIn, current_user: str = Depends(get_current_user)):
    _require_enabled()
    _run(team_ops.share_analysis, _store(), current_user, structure_id, payload.analysis_id, payload.share)
    return {"ok": True}


# ─────────────────────────────────────────────── coach (E2-E3)

class PilotInviteIn(BaseModel):
    guardian_certified: bool = False
    max_uses: Optional[int] = None
    expires_days: int = 30


@router.post("/api/team/{structure_id}/invites")
async def team_create_invite(structure_id: str, payload: PilotInviteIn, current_user: str = Depends(get_current_user)):
    _require_enabled()
    inv = _run(team_ops.create_pilot_invite, _store(), current_user, structure_id, payload.model_dump())
    return {"code": inv["code"], "expires_at": inv.get("expires_at"), "guardian_certified": inv.get("guardian_certified")}


@router.get("/api/team/{structure_id}/overview")
async def team_overview(structure_id: str, current_user: str = Depends(get_current_user)):
    _require_enabled()
    return _run(team_ops.team_overview, _store(), current_user, structure_id)


@router.get("/api/team/{structure_id}/pilots/{pilot_id}/sessions")
async def team_pilot_sessions(structure_id: str, pilot_id: str, current_user: str = Depends(get_current_user)):
    _require_enabled()
    return _run(team_ops.pilot_sessions, _store(), current_user, structure_id, pilot_id)


@router.post("/api/team/{structure_id}/pilots/{pilot_id}/remove")
async def team_remove_pilot(structure_id: str, pilot_id: str, current_user: str = Depends(get_current_user)):
    _require_enabled()
    return _run(team_ops.remove_pilot, _store(), current_user, structure_id, pilot_id)


# ─────────────────────────────────────────────── admin

class RequestUpdateIn(BaseModel):
    status: Optional[str] = None
    admin_note: Optional[str] = None


class StructureIn(BaseModel):
    name: str
    kind: str = "ecole"
    trial_weeks: int = team_ops.DEFAULT_TRIAL_WEEKS
    max_pilots: Optional[int] = None
    max_coaches: Optional[int] = None
    max_karts: Optional[int] = None
    coach_email: Optional[str] = None
    contact_request_id: Optional[str] = None


@router.get("/api/admin/team")
async def admin_team(ctx: Dict[str, Any] = Depends(require_permission("team"))):
    data = _run(team_ops.admin_overview, _store())
    return {**data, "enabled": team_space_enabled()}


@router.patch("/api/admin/team/requests/{request_id}")
async def admin_team_request(request_id: str, payload: RequestUpdateIn, ctx: Dict[str, Any] = Depends(require_permission("team"))):
    _run(team_ops.update_contact_request, _store(), request_id, payload.status, payload.admin_note)
    return {"ok": True}


@router.post("/api/admin/team/structures")
async def admin_team_create(payload: StructureIn, ctx: Dict[str, Any] = Depends(require_permission("team"))):
    out = _run(team_ops.admin_create_structure, _store(), ctx["user_id"], payload.model_dump())
    code = out["coach_invite"]["code"]
    return {"structure": out["structure"], "coach_code": code, "coach_link": f"https://www.apexai.racing/rejoindre/{code}"}


@router.patch("/api/admin/team/structures/{structure_id}")
async def admin_team_update(structure_id: str, payload: Dict[str, Any], ctx: Dict[str, Any] = Depends(require_permission("team"))):
    _run(team_ops.admin_update_structure, _store(), structure_id, payload)
    return {"ok": True}
