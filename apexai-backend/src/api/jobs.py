"""
Analyses en tâche de fond.

Le navigateur dépose le fichier et reçoit aussitôt un numéro de tâche ; il
suit ensuite la progression RÉELLE du serveur (étape en cours, place dans la
file) jusqu'au résultat. Plus aucune requête HTTP ne reste ouverte pendant
le calcul : fini les délais dépassés côté navigateur.

- File d'attente : un seul calcul à la fois (un exécuteur à un fil). Deux
  analyses ne se disputent plus le processeur ; la suivante attend son tour
  et l'app affiche sa place dans la file.
- Signature : empreinte SHA-256 du fichier + paramètres + mode. Un fichier
  déjà analysé n'est jamais recalculé (résultat gardé en mémoire et dans
  Redis s'il est configuré) ; un dépôt identique pendant le calcul rejoint
  la tâche en cours au lieu d'en lancer une seconde.
- Mode « light » : 2e séance d'une comparaison (tours, virages, traces).
  Ni quota, ni sauvegarde dans Sessions (décidé avec Yanis le 7/11).

Tâches gardées 30 minutes en mémoire : le serveur tourne sur un seul
processus. Après un redémarrage, l'app reçoit 404 et propose de relancer.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import os
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from .config import settings
from .models import AnalysisResponse
from .rate_limiter import get_user_token_or_ip, limiter
from .utils import sanitize_json_data, validate_csv_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis-jobs"])

# Version du calcul : à changer quand le pipeline change de résultat, pour ne
# pas resservir un ancien résultat mis en cache.
PIPELINE_VERSION = "2026-11-07b"

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")
_JOBS: Dict[str, "Job"] = {}
_QUEUE: List[str] = []  # tâches en attente ou en cours, dans l'ordre
_INFLIGHT: Dict[str, str] = {}  # signature -> job_id
_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_CACHE_MAX = 24
_JOB_TTL_S = 30 * 60
_REDIS_PREFIX = "apexai:result:"
_TASKS: set = set()  # références fortes : une tâche asyncio non référencée peut être ramassée
_REDIS_TTL_S = 7 * 24 * 3600


@dataclass
class Job:
    id: str
    signature: str
    mode: str
    user_id: Optional[str]
    filename: str
    status: str = "queued"  # queued | running | done | error
    progress: int = 0
    step: str = "En file d'attente"
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    cached: bool = False
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    def public(self) -> Dict[str, Any]:
        position = _QUEUE.index(self.id) if self.id in _QUEUE and self.status == "queued" else 0
        now = time.time()
        out: Dict[str, Any] = {
            "job_id": self.id,
            "status": self.status,
            "mode": self.mode,
            "progress": self.progress,
            "step": self.step,
            "position": position,
            "cached": self.cached,
            "elapsed_s": round((self.finished_at or now) - (self.started_at or self.created_at), 1),
        }
        if self.status == "done":
            out["result"] = self.result
        if self.status == "error":
            out["error"] = self.error
        return out


# ─── Signature et cache ──────────────────────────────────────────────────────

def signature(content: bytes, params: Dict[str, Any], mode: str) -> str:
    h = hashlib.sha256()
    h.update(content)
    h.update(json.dumps({"p": params, "m": mode, "v": PIPELINE_VERSION}, sort_keys=True).encode())
    return h.hexdigest()


async def _cache_get(request: Request, sig: str) -> Optional[Dict[str, Any]]:
    hit = _CACHE.get(sig)
    if hit is not None:
        _CACHE.move_to_end(sig)
        return hit
    redis = getattr(request.app.state, "redis", None)
    if redis:
        try:
            raw = await redis.get(_REDIS_PREFIX + sig)
            if raw:
                data = json.loads(raw)
                _cache_put_memory(sig, data)
                return data
        except Exception as exc:
            logger.warning("cache redis indisponible : %s", exc)
    return None


def _cache_put_memory(sig: str, result: Dict[str, Any]) -> None:
    _CACHE[sig] = result
    _CACHE.move_to_end(sig)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)


async def _cache_put(redis: Any, sig: str, result: Dict[str, Any]) -> None:
    _cache_put_memory(sig, result)
    if redis:
        try:
            await redis.setex(_REDIS_PREFIX + sig, _REDIS_TTL_S, json.dumps(result, default=str))
        except Exception as exc:
            logger.warning("cache redis : écriture impossible : %s", exc)


def _fresh_copy(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Résultat resservi depuis le cache, sous un NOUVEL identifiant : l'identifiant
    est la clé de la ligne enregistrée dans Sessions ; deux pilotes qui déposent
    le même fichier ne doivent jamais se disputer la même ligne.
    """
    out = copy.copy(result)
    out["analysis_id"] = str(uuid.uuid4())
    return out


def _purge() -> None:
    now = time.time()
    for jid in [j for j, job in _JOBS.items() if job.finished_at and now - job.finished_at > _JOB_TTL_S]:
        _JOBS.pop(jid, None)


# ─── Exécution ───────────────────────────────────────────────────────────────

def _work(job: Job, content: bytes, saved_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Calcul complet, dans le fil unique de l'exécuteur."""
    from src.api import progress
    from src.api.services import _run_analysis_pipeline_sync
    from src.core.session_header import read_session_header
    from datetime import datetime

    def on_progress(pct: int, label: str) -> None:
        job.progress = max(job.progress, min(97, pct))
        job.step = label

    job.status = "running"
    job.started_at = time.time()
    on_progress(4, "Lecture du fichier")
    progress.bind(on_progress)
    analysis_id = str(uuid.uuid4())
    temp_path = os.path.join(settings.TEMP_DIR, f"{analysis_id}_{os.path.basename(saved_name or 'session.csv')}")
    try:
        with open(temp_path, "wb") as f:
            f.write(content)
        header = read_session_header(temp_path)
        result = _run_analysis_pipeline_sync(
            temp_path,
            header["beacon_markers"],
            analysis_id,
            datetime.now(),
            params.get("laps") or None,
            params.get("condition", "dry"),
            params.get("temperature"),
            params.get("session_name"),
            header["circuit_name"],
            job.mode == "light",
        )
        if job.mode == "full" and job.user_id:
            _kart_hook(job.user_id, temp_path, result, header["circuit_name"], analysis_id)
        return result
    finally:
        progress.bind(None)
        try:
            os.remove(temp_path)
        except OSError:
            pass


def _kart_hook(user_id: str, temp_path: str, result: Dict[str, Any], circuit_name: Optional[str], analysis_id: str) -> None:
    """Mon Kart : compteurs d'usure alimentés par la séance (comme /analyze)."""
    try:
        from src.api.kart_routes import is_mon_kart_enabled
        from src.api.kart_service import KartService
        from src.core.kart_mechanical import parse_kart_mechanical

        if is_mon_kart_enabled() and KartService.is_racer_or_team(user_id):
            k_res = parse_kart_mechanical(temp_path)
            if k_res.get("success"):
                metrics = dict(k_res["aggregates"] or {})
                tf = result.get("track_features") if isinstance(result, dict) else None
                if tf:
                    metrics["track_features"] = tf
                if circuit_name and not metrics.get("circuit_name"):
                    metrics["circuit_name"] = circuit_name
                KartService.upsert_session(
                    user_id=user_id,
                    signature=k_res["signature"],
                    imported_via="analyze",
                    metrics=metrics,
                    analysis_id=analysis_id,
                )
    except Exception as exc:
        logger.warning("[%s] Mon Kart : compteurs non mis à jour : %s", analysis_id, exc)


async def _run(job: Job, content: bytes, filename: str, params: Dict[str, Any], redis: Any) -> None:
    from src.core.xrk_loader import normalize_upload
    try:
        content, saved_name = await normalize_upload(content, filename)
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(_EXECUTOR, _work, job, content, saved_name, params)
        job.step = "Envoi du résultat"
        job.progress = 98
        result = sanitize_json_data(AnalysisResponse(**raw).model_dump())
        if not isinstance(result, dict):
            raise RuntimeError("résultat invalide")
        await _cache_put(redis, job.signature, result)
        if job.mode == "full" and job.user_id:
            try:
                from src.core.subscription_service import increment_analysis_count

                increment_analysis_count(job.user_id)
            except Exception as exc:
                logger.warning("compteur d'analyses : %s", exc)
        job.result = result
        job.progress = 100
        job.step = "Terminé"
        job.status = "done"
        logger.info("[job %s] terminé en %.1fs (%s)", job.id, time.time() - (job.started_at or job.created_at), job.mode)
    except ValueError as exc:
        job.status = "error"
        job.error = {"error": "processing_error", "message": str(exc)}
    except Exception as exc:
        logger.error("[job %s] échec : %s", job.id, exc, exc_info=True)
        job.status = "error"
        job.error = {
            "error": "internal_error",
            "message": "Une erreur s'est produite pendant l'analyse. Réessaie dans un instant.",
        }
    finally:
        job.finished_at = time.time()
        if job.id in _QUEUE:
            _QUEUE.remove(job.id)
        if _INFLIGHT.get(job.signature) == job.id:
            _INFLIGHT.pop(job.signature, None)


# ─── Routes ──────────────────────────────────────────────────────────────────

def _user_id(authorization: Optional[str]) -> Optional[str]:
    from .routes import _get_user_id_from_authorization

    return _get_user_id_from_authorization(authorization)


@router.post("/jobs", summary="Déposer un fichier à analyser (tâche de fond)")
@limiter.limit("20/minute", key_func=get_user_token_or_ip)
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    mode: str = Form("full", description="full | light (2e séance d'une comparaison)"),
    lap_filter: Optional[str] = Form(None),
    track_condition: str = Form("auto"),
    track_temperature: Optional[str] = Form(None),
    session_name: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    _purge()
    mode = "light" if (mode or "").strip().lower() == "light" else "full"
    user_id = _user_id(authorization)

    if mode == "full" and user_id:
        from src.core.subscription_service import check_analysis_limit

        if not check_analysis_limit(user_id):
            raise HTTPException(
                status_code=403,
                detail={
                    "success": False,
                    "error": "limit_reached",
                    "message": (
                        "Vous avez atteint la limite d'analyses de votre abonnement ce mois-ci. "
                        "Passez au plan Racer ou Team pour des analyses illimitées."
                    ),
                },
            )

    content = await file.read()
    error = await validate_csv_file(file, content_override=content)
    if error:
        raise HTTPException(status_code=400, detail={"success": False, "error": "Validation error", "message": error})

    laps: List[int] = []
    if lap_filter and lap_filter.strip():
        try:
            parsed = json.loads(lap_filter)
            if isinstance(parsed, list):
                laps = sorted(int(x) for x in parsed if isinstance(x, (int, float)))
        except (TypeError, ValueError):
            laps = []
    cond = (track_condition or "auto").strip().lower()
    if cond not in ("dry", "damp", "wet", "rain", "auto"):
        cond = "auto"
    temp_c: Optional[float] = None
    if track_temperature and track_temperature.strip():
        try:
            temp_c = float(track_temperature.strip().replace(",", "."))
        except ValueError:
            temp_c = None
    params = {
        "laps": laps,
        "condition": "dry" if mode == "light" else cond,
        "temperature": None if mode == "light" else temp_c,
        "session_name": (session_name or "").strip() or None,
    }
    # Le nom de séance ne change pas le calcul : il reste hors de la signature.
    sig = signature(content, {k: v for k, v in params.items() if k != "session_name"}, mode)
    filename = file.filename or "session.csv"

    # 1. Déjà analysé : résultat immédiat, sans recalcul ni quota.
    cached = await _cache_get(request, sig)
    if cached is not None:
        job = Job(id=str(uuid.uuid4()), signature=sig, mode=mode, user_id=user_id, filename=filename)
        res = _fresh_copy(cached)
        if params["session_name"] and isinstance(res.get("session_conditions"), dict):
            res["session_conditions"] = {**res["session_conditions"], "session_name": params["session_name"]}
        job.result, job.status, job.progress, job.step, job.cached = res, "done", 100, "Déjà analysé", True
        job.finished_at = time.time()
        _JOBS[job.id] = job
        logger.info("[job %s] signature connue : résultat resservi (%s)", job.id, mode)
        return JSONResponse(content=job.public())

    # 2. Le même fichier est déjà en cours : on rejoint cette tâche.
    running_id = _INFLIGHT.get(sig)
    if running_id and running_id in _JOBS and _JOBS[running_id].status in ("queued", "running"):
        return JSONResponse(content=_JOBS[running_id].public())

    # 3. Nouvelle tâche, en file.
    job = Job(id=str(uuid.uuid4()), signature=sig, mode=mode, user_id=user_id, filename=filename)
    _JOBS[job.id] = job
    _QUEUE.append(job.id)
    _INFLIGHT[sig] = job.id
    if len(_QUEUE) > 1:
        job.step = "En file d'attente"
    redis = getattr(request.app.state, "redis", None)
    task = asyncio.create_task(_run(job, content, filename, params, redis))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    logger.info("[job %s] créé (%s, %d o, place %d)", job.id, mode, len(content), len(_QUEUE) - 1)
    return JSONResponse(status_code=202, content={k: v for k, v in job.public().items() if k != "result"})


@router.get("/jobs/{job_id}", summary="Progression d'une analyse en tâche de fond")
async def get_job(job_id: str):
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"error": "job_not_found", "message": "Cette analyse n'est plus suivie par le serveur. Relance-la."},
        )
    return JSONResponse(content=job.public())
