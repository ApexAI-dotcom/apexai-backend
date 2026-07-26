#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Calendrier du pilote (vie sportive)

Courses, entraînements, séances de coaching et échéances administratives.
Calendrier PERSONNEL : chaque pilote ne voit et ne modifie que ses propres
échéances. L'appartenance est toujours imposée côté serveur à partir du jeton —
jamais lue depuis la requête — pour qu'un identifiant ne puisse pas être
falsifié.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from supabase import Client, create_client

from .auth import get_current_user
from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

SUPABASE_URL = os.getenv("SUPABASE_URL") or getattr(settings, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
)

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_SERVICE_ROLE_KEY not in ("", "ton_service_role_key"):
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

EVENT_TYPES = ("race", "training", "coaching", "deadline", "other")
TABLE = "pilot_events"

# Colonnes renvoyées au frontend (jamais "*" : on maîtrise le contrat).
FIELDS = (
    "id, title, event_type, starts_at, ends_at, all_day, "
    "circuit_name, location, notes, completed, created_at, updated_at"
)


class EventPayload(BaseModel):
    """Un événement du calendrier, tel que saisi par le pilote."""

    title: str = Field(..., min_length=1, max_length=140)
    event_type: str = Field(default="training")
    starts_at: datetime
    ends_at: Optional[datetime] = None
    all_day: bool = False
    circuit_name: Optional[str] = Field(default=None, max_length=140)
    location: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)
    completed: bool = False

    @field_validator("event_type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        v = (v or "training").strip().lower()
        if v not in EVENT_TYPES:
            raise ValueError(f"type d'événement inconnu (attendu : {', '.join(EVENT_TYPES)})")
        return v

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("le titre ne peut pas être vide")
        return v


def _require_db() -> Client:
    if supabase is None:
        raise HTTPException(status_code=503, detail="Service temporairement indisponible")
    return supabase


def _to_row(payload: EventPayload, user_id: str) -> Dict[str, Any]:
    if payload.ends_at and payload.ends_at < payload.starts_at:
        raise HTTPException(status_code=400, detail="La fin ne peut pas précéder le début.")
    return {
        "user_id": user_id,  # imposé par le serveur, jamais par le client
        "title": payload.title,
        "event_type": payload.event_type,
        "starts_at": payload.starts_at.isoformat(),
        "ends_at": payload.ends_at.isoformat() if payload.ends_at else None,
        "all_day": payload.all_day,
        "circuit_name": (payload.circuit_name or None),
        "location": (payload.location or None),
        "notes": (payload.notes or None),
        "completed": payload.completed,
    }


@router.get("/events")
async def list_events(
    current_user: str = Depends(get_current_user),
    start: Optional[datetime] = Query(None, description="Borne inférieure (incluse)"),
    end: Optional[datetime] = Query(None, description="Borne supérieure (incluse)"),
    limit: int = Query(500, ge=1, le=1000),
):
    """Événements du pilote, du plus proche au plus lointain."""
    db = _require_db()
    try:
        q = db.table(TABLE).select(FIELDS).eq("user_id", current_user)
        if start:
            q = q.gte("starts_at", start.isoformat())
        if end:
            q = q.lte("starts_at", end.isoformat())
        res = q.order("starts_at", desc=False).limit(limit).execute()
        return {"events": res.data or []}
    except Exception as e:
        logger.exception("list_events failed for user_id=%s: %s", current_user, e)
        raise HTTPException(status_code=500, detail="Impossible de charger le calendrier")


@router.get("/upcoming")
async def upcoming(
    current_user: str = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(5, ge=1, le=50),
):
    """
    Prochaines échéances — alimente le bandeau du tableau de bord.

    On exclut ce qui est déjà fait et ce qui est passé : le pilote veut savoir
    ce qui arrive, pas relire son historique.
    """
    db = _require_db()
    now = datetime.now(timezone.utc)
    try:
        res = (
            db.table(TABLE)
            .select(FIELDS)
            .eq("user_id", current_user)
            .eq("completed", False)
            .gte("starts_at", now.isoformat())
            .lte("starts_at", (now + timedelta(days=days)).isoformat())
            .order("starts_at", desc=False)
            .limit(limit)
            .execute()
        )
        events: List[Dict[str, Any]] = res.data or []
        for ev in events:
            try:
                start_dt = datetime.fromisoformat(str(ev["starts_at"]).replace("Z", "+00:00"))
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                ev["days_until"] = max(0, (start_dt - now).days)
            except Exception:
                ev["days_until"] = None
        return {"events": events}
    except Exception as e:
        logger.exception("upcoming failed for user_id=%s: %s", current_user, e)
        raise HTTPException(status_code=500, detail="Impossible de charger les échéances")


@router.post("/events", status_code=201)
async def create_event(payload: EventPayload, current_user: str = Depends(get_current_user)):
    db = _require_db()
    try:
        res = db.table(TABLE).insert(_to_row(payload, current_user)).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Création impossible")
        logger.info("calendar: event created user_id=%s type=%s", current_user, payload.event_type)
        return {"event": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_event failed for user_id=%s: %s", current_user, e)
        raise HTTPException(status_code=500, detail="Impossible d'enregistrer l'événement")


@router.put("/events/{event_id}")
async def update_event(
    event_id: str, payload: EventPayload, current_user: str = Depends(get_current_user)
):
    db = _require_db()
    row = _to_row(payload, current_user)
    row.pop("user_id", None)  # l'appartenance ne se modifie jamais
    try:
        # Le filtre sur user_id est la garantie qu'on ne modifie pas l'événement
        # d'un autre pilote, même avec un identifiant valide.
        res = (
            db.table(TABLE)
            .update(row)
            .eq("id", event_id)
            .eq("user_id", current_user)
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Événement introuvable")
        return {"event": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("update_event failed id=%s user_id=%s: %s", event_id, current_user, e)
        raise HTTPException(status_code=500, detail="Impossible de modifier l'événement")


@router.delete("/events/{event_id}")
async def delete_event(event_id: str, current_user: str = Depends(get_current_user)):
    db = _require_db()
    try:
        res = (
            db.table(TABLE)
            .delete()
            .eq("id", event_id)
            .eq("user_id", current_user)
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Événement introuvable")
        return {"deleted": True, "id": event_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("delete_event failed id=%s user_id=%s: %s", event_id, current_user, e)
        raise HTTPException(status_code=500, detail="Impossible de supprimer l'événement")
