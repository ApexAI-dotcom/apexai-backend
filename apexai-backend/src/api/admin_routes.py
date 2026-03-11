#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Admin routes (TEMPORAIRES)
POST /api/admin/run-migrations : exécute la migration 20260311 analyses (service_role only).

Vérification manuelle DB-003 (si table analyses manquante) :
  - Supabase → SQL Editor → SELECT * FROM supabase_migrations.schema_migrations (ou équivalent)
  - Si 20260311000000 absent : exécuter manuellement le contenu de
    supabase/migrations/20260311000000_analyses.sql dans SQL Editor.
  - Ou appeler POST /api/admin/run-migrations avec header X-Admin-Key = service_role
    (nécessite DATABASE_URL = connexion Postgres directe).
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
)


def _require_service_role(x_admin_key: str | None = Header(None, alias="X-Admin-Key")) -> None:
    """Vérifie que la requête est authentifiée par la clé service_role."""
    if not SERVICE_ROLE_KEY or SERVICE_ROLE_KEY == "ton_service_role_key":
        raise HTTPException(status_code=501, detail="Admin not configured")
    if not x_admin_key or x_admin_key.strip() != SERVICE_ROLE_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/run-migrations")
async def run_migrations(
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
) -> JSONResponse:
    """
    TEMPORAIRE. Exécute la migration 20260311000000_analyses.sql (table analyses + RLS).
    Auth : header X-Admin-Key = SUPABASE_SERVICE_ROLE_KEY.
    """
    _require_service_role(x_admin_key)

    database_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL", "")
    if not database_url:
        logger.warning("run_migrations: DATABASE_URL not set")
        return JSONResponse(
            status_code=503,
            content={
                "error": "DATABASE_URL not set",
                "message": "Définir DATABASE_URL (connexion Postgres directe) ou exécuter la migration manuellement dans Supabase SQL Editor.",
            },
        )

    migration_name = "20260311000000_analyses.sql"
    project_root = Path(__file__).parent.parent.parent.resolve()
    migration_path = project_root / "supabase" / "migrations" / migration_name
    if not migration_path.exists():
        logger.warning("run_migrations: file not found %s", migration_path)
        raise HTTPException(status_code=500, detail=f"Migration file not found: {migration_name}")

    sql = migration_path.read_text(encoding="utf-8")

    def strip_comments(stmt: str) -> str:
        """Retire les lignes de commentaire en tête."""
        lines = [line for line in stmt.splitlines() if not line.strip().startswith("--")]
        return "\n".join(lines).strip()

    statements = []
    for s in sql.split(";"):
        stmt = strip_comments(s.strip())
        if stmt:
            statements.append(stmt)

    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cur = conn.cursor()
        for stmt in statements:
            cur.execute(stmt)
        cur.close()
        conn.close()
        logger.info("migration_executed", extra={"migration": migration_name})
        return JSONResponse(content={"ok": True, "migration": migration_name})
    except ImportError:
        logger.warning("run_migrations: psycopg2 not installed")
        return JSONResponse(
            status_code=503,
            content={"error": "psycopg2 not installed", "message": "pip install psycopg2-binary"},
        )
    except Exception as e:
        logger.exception("run_migrations failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
