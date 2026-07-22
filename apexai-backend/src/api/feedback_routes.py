#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Boîte à recommandations (feedback privé pilote <-> admin)

Le pilote envoie ses idées, bugs du terrain et questions depuis l'app.
Les échanges restent CONFIDENTIELS : un pilote ne voit que ses propres
messages, seul l'admin voit l'ensemble et peut répondre.

Auth : JWT Bearer via get_current_user (SEC-001).
"""

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from .auth import get_current_user
from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

SUPABASE_URL = os.getenv("SUPABASE_URL") or getattr(settings, "SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
)
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "moreauy58@gmail.com").strip().lower()

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_SERVICE_ROLE_KEY not in ("", "ton_service_role_key"):
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
else:
    logger.warning("Supabase client is None in feedback_routes")

MAX_SUBJECT = 140
MAX_BODY = 4000
VALID_CATEGORIES = {"idea", "bug", "question", "other"}
VALID_STATUSES = {"new", "read", "in_progress", "done", "archived"}


class FeedbackCreate(BaseModel):
    category: str = Field(default="idea")
    subject: str
    body: str
    context: Optional[Dict[str, Any]] = None


class FeedbackAdminUpdate(BaseModel):
    status: Optional[str] = None
    admin_reply: Optional[str] = Field(default=None, alias="adminReply")

    class Config:
        populate_by_name = True


def _is_admin(user_id: str) -> bool:
    """Autorisé si le compte porte un rôle avec la permission "feedback".

    Le rôle vient de la table admin_roles (délégable à des collaborateurs) ;
    l'email fondateur reste un filet de sécurité.
    """
    try:
        from .admin_panel_routes import get_admin_role, PERMISSIONS
        role = get_admin_role(user_id)
        if role and "feedback" in PERMISSIONS.get(role, set()):
            return True
    except Exception as e:
        logger.warning(f"feedback: role check failed: {e}")
    if not supabase:
        return False
    try:
        res = supabase.auth.admin.get_user_by_id(user_id)
        email = getattr(getattr(res, "user", None), "email", None)
        return bool(email) and email.strip().lower() == ADMIN_EMAIL
    except Exception as e:
        logger.warning(f"feedback: admin check failed: {e}")
        return False


@router.post("")
async def create_feedback(payload: FeedbackCreate, current_user: str = Depends(get_current_user)):
    """Envoyer une recommandation / un bug / une question."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Service indisponible")

    subject = (payload.subject or "").strip()
    body = (payload.body or "").strip()
    if not subject or not body:
        raise HTTPException(status_code=400, detail="Sujet et message sont obligatoires.")
    if len(subject) > MAX_SUBJECT or len(body) > MAX_BODY:
        raise HTTPException(status_code=400, detail="Message trop long.")

    category = payload.category if payload.category in VALID_CATEGORIES else "other"
    try:
        res = supabase.table("feedback_messages").insert({
            "user_id": current_user,
            "category": category,
            "subject": subject,
            "body": body,
            "context": payload.context,
        }).execute()
        logger.info(f"feedback created by {current_user} ({category})")
        return {"success": True, "message": res.data[0] if res.data else None}
    except Exception as e:
        logger.error(f"create_feedback failed: {e}")
        raise HTTPException(status_code=500, detail="Envoi impossible.")


@router.get("/mine")
async def list_my_feedback(current_user: str = Depends(get_current_user)):
    """Historique de MES messages (avec la réponse de l'admin si elle existe)."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Service indisponible")
    try:
        res = (
            supabase.table("feedback_messages")
            .select("id, category, subject, body, status, admin_reply, replied_at, created_at")
            .eq("user_id", current_user)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return {"messages": res.data or []}
    except Exception as e:
        logger.error(f"list_my_feedback failed: {e}")
        return {"messages": []}


@router.get("/admin")
async def list_all_feedback(status: Optional[str] = None, current_user: str = Depends(get_current_user)):
    """[ADMIN] Tous les retours pilotes, avec l'email de l'auteur."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Service indisponible")
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à l'administrateur.")
    try:
        query = supabase.table("feedback_messages").select("*")
        if status and status in VALID_STATUSES:
            query = query.eq("status", status)
        res = query.order("created_at", desc=True).limit(200).execute()
        messages: List[Dict[str, Any]] = res.data or []

        # Enrichit avec l'email de l'auteur (lecture admin, best-effort)
        for m in messages:
            try:
                u = supabase.auth.admin.get_user_by_id(m["user_id"])
                m["user_email"] = getattr(getattr(u, "user", None), "email", None)
            except Exception:
                m["user_email"] = None
        return {"messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_all_feedback failed: {e}")
        raise HTTPException(status_code=500, detail="Lecture impossible.")


@router.put("/admin/{message_id}")
async def update_feedback(message_id: str, payload: FeedbackAdminUpdate,
                          current_user: str = Depends(get_current_user)):
    """[ADMIN] Répondre à un retour et/ou changer son statut."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Service indisponible")
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à l'administrateur.")

    updates: Dict[str, Any] = {}
    if payload.status:
        if payload.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Statut invalide.")
        updates["status"] = payload.status
    if payload.admin_reply is not None:
        reply = payload.admin_reply.strip()
        if len(reply) > MAX_BODY:
            raise HTTPException(status_code=400, detail="Réponse trop longue.")
        updates["admin_reply"] = reply or None
        updates["replied_at"] = "now()" if reply else None
        if reply and not payload.status:
            updates["status"] = "done"
    if not updates:
        raise HTTPException(status_code=400, detail="Rien à mettre à jour.")

    try:
        # replied_at : on laisse Postgres poser l'horodatage
        if updates.get("replied_at") == "now()":
            from datetime import datetime, timezone
            updates["replied_at"] = datetime.now(timezone.utc).isoformat()
        res = supabase.table("feedback_messages").update(updates).eq("id", message_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Message introuvable.")
        return {"success": True, "message": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_feedback failed: {e}")
        raise HTTPException(status_code=500, detail="Mise à jour impossible.")
