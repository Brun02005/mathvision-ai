"""
REST API.

Endpoints are plain `def` on purpose: they block (waiting for the solver
process, the OCR service and SQLite), and FastAPI runs sync endpoints in a
thread pool. Inside `async def` that wait would freeze the event loop and
every other request with it.
"""
import json
import logging
import os
import threading
import uuid
from contextlib import contextmanager

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

import config
import database
import models
import schemas
import pipeline
from auth import current_user
from billing import usage
from interpreter import llm, metering
from ocr.latex_extractor import OCRUnavailableError, ocr_status
from pipeline import OCRError, process_exercise_file, solve
from ratelimit import RateLimiter
from solver_pool import SolverBusy, SolverCrashed, SolverTimeout

router = APIRouter()
logger = logging.getLogger(__name__)

API_VERSION = "1.3.0"
CHUNK = 1024 * 1024


def _to_response(res: dict, exercise: models.Exercise | None, mode: str) -> dict:
    return {
        "id": exercise.id if exercise else None,
        "extracted_latex": res.get("extracted_latex", ""),
        "domain_classification": res.get("domain_classification", ""),
        # Exam mode hides the steps, but history always keeps the full solution
        "steps": res.get("steps", []) if mode == "Teacher" or not res.get("solved", True) else [],
        "final_result_latex": res.get("final_result_latex", ""),
        "graph_data": res.get("graph_data"),
        "solved": res.get("solved", True),
        "verified": res.get("verified"),
        "method": res.get("method"),
        "interpretation": res.get("interpretation"),
        "created_at": exercise.created_at if exercise else None,
    }


def _persist(db: Session, res: dict, user: models.User, image_path: str | None = None) -> models.Exercise | None:
    """Save the solved exercise. A DB failure must not lose the user's solution, so it only logs."""
    try:
        ex = models.Exercise(
            user_id=user.id,
            original_image_path=image_path,
            extracted_latex=res["extracted_latex"],
            domain_classification=res["domain_classification"],
            symbolic_representation=res.get("symbolic_representation", ""),
            solution_steps_json=json.dumps(res.get("steps", []), ensure_ascii=False),
            final_result_latex=res["final_result_latex"],
            graph_data_json=json.dumps(res["graph_data"], ensure_ascii=False) if res.get("graph_data") else None,
        )
        db.add(ex)
        db.commit()
        db.refresh(ex)
        return ex
    except Exception as e:
        db.rollback()
        logger.warning(f"DB persist skipped: {e}")
        return None


_MAGIC = {
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".bmp": b"BM",
    ".pdf": b"%PDF-",
}


def _content_matches(ext: str, head: bytes) -> bool:
    """The extension is chosen by the client: check the file's first bytes actually are that format."""
    if ext == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return head.startswith(_MAGIC[ext])


def _save_upload(file: UploadFile) -> str:
    """Store the upload under a random name (never trust the client filename) enforcing type and size."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"Formato no soportado. Usá: {', '.join(sorted(config.ALLOWED_EXTENSIONS))}")

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    path = os.path.join(config.UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    try:
        with open(path, "wb") as out:
            while chunk := file.file.read(CHUNK):
                if written == 0 and not _content_matches(ext, chunk):
                    raise HTTPException(415, f"El contenido del archivo no corresponde a un {ext}.")
                written += len(chunk)
                if written > limit:
                    raise HTTPException(413, f"El archivo supera el máximo de {config.MAX_UPLOAD_MB} MB.")
                out.write(chunk)
    except HTTPException:
        os.remove(path)
        raise
    if written == 0:
        os.remove(path)
        raise HTTPException(400, "El archivo está vacío.")
    return path


@contextmanager
def _solver_errors(context: str, outcome: dict | None = None):
    """Translate pipeline failures into HTTP errors the user can act on."""
    try:
        yield
    except (OCRError, ValueError) as e:
        raise HTTPException(422, str(e)) from e
    except SolverTimeout:
        if outcome is not None:
            outcome["expensive"] = True  # a worker was busy for the whole time limit
        raise HTTPException(422, f"El ejercicio tardó más de {config.SOLVE_TIMEOUT_SECONDS:g} s en resolverse "
                                 "y se canceló. Probá simplificarlo o dividirlo en partes.") from None
    except SolverBusy:
        raise HTTPException(503, "El servidor está resolviendo muchos ejercicios a la vez. Probá de nuevo en unos segundos.",
                            headers={"Retry-After": "10"}) from None
    except OCRUnavailableError as e:
        raise HTTPException(503, str(e), headers={"Retry-After": "60"}) from None
    except SolverCrashed:
        if outcome is not None:
            outcome["expensive"] = True  # the worker died and has to be respawned
        logger.error(f"{context}: solver worker crashed")
        raise HTTPException(500, "Error interno al resolver el ejercicio.") from None
    except Exception:
        logger.error(f"{context} error", exc_info=True)
        raise HTTPException(500, "Error interno al resolver el ejercicio.") from None


# Burst protection per account, on top of the daily quota: a person does not send more
# than a few exercises a minute; a script does. (In-memory: one server process, see Dockerfile.)
_per_user = RateLimiter(limit=config.USER_REQUESTS_PER_MINUTE, window_seconds=60)
# One exercise in progress per account: a single account must not occupy every solver worker
_in_flight: set[str] = set()
_in_flight_lock = threading.Lock()


@contextmanager
def _one_at_a_time(user: models.User):
    with _in_flight_lock:
        if user.id in _in_flight:
            raise HTTPException(429, {"code": "busy", "message": "Ya estamos resolviendo otro ejercicio tuyo. "
                                                                 "Esperá a que termine."})
        _in_flight.add(user.id)
    try:
        yield
    finally:
        with _in_flight_lock:
            _in_flight.discard(user.id)


@contextmanager
def _quota(db: Session, user: models.User):
    """
    Reserve one exercise of today's quota (and one AI use, if any left) around a solve.
    A failed attempt gives the exercise back only if it was cheap: one that held a worker
    for the whole time limit or called Gemini (OCR, AI) is charged, otherwise failing on
    purpose would be a free way to use the servers and the paid API. Unused AI quota is
    given back; the AI tokens actually spent are always recorded.
    Yields (ai_allowed, outcome); the caller sets outcome["solved"].
    """
    if not _per_user.allow(user.id):
        raise HTTPException(429, {"code": "too_fast", "message": "Estás enviando ejercicios muy rápido. Esperá un minuto."},
                            headers={"Retry-After": "60"})
    day = usage.reserve(db, user, usage.EXERCISES)
    if day is None:
        limits = usage.limits_for(user)
        message = (f"Llegaste al límite de uso justo de {limits.exercises} ejercicios por día."
                   if user.is_pro() else
                   f"Usaste los {limits.exercises} ejercicios gratis de hoy. Se renuevan mañana, "
                   "o pasate a Pro para seguir ahora.")
        raise HTTPException(429, {"code": "daily_limit", "message": message})
    ai_day = usage.reserve(db, user, usage.AI)
    outcome = {"solved": False, "expensive": False}
    with metering.metering() as meter:
        try:
            with _one_at_a_time(user):
                yield ai_day is not None, outcome
        finally:
            if not outcome["solved"] and not outcome["expensive"] and meter.calls == 0:
                usage.release(db, user, usage.EXERCISES, day)
            if ai_day is not None and meter.assistant_calls == 0:
                usage.release(db, user, usage.AI, ai_day)
            usage.record_ai_tokens(db, user, meter.input_tokens, meter.output_tokens)


@router.post("/solve-text", response_model=schemas.SolveResponse)
def solve_from_text(
    latex_expression: str = Form(...),
    mode: schemas.Mode = Form("Teacher"),
    operation: schemas.Operation = Form("auto"),
    user: models.User = Depends(current_user),
    db: Session = Depends(database.get_db),
):
    with _quota(db, user) as (ai_allowed, outcome):
        with _solver_errors("solve-text", outcome):
            res = solve(latex_expression, "Teacher", operation, ai_allowed)
        outcome["solved"] = res["solved"]
    return _to_response(res, _persist(db, res, user) if res["solved"] else None, mode)


@router.post("/upload", response_model=schemas.SolveResponse)
def upload_file(
    mode: schemas.Mode = Form("Teacher"),
    operation: schemas.Operation = Form("auto"),
    file: UploadFile = File(...),
    user: models.User = Depends(current_user),
    db: Session = Depends(database.get_db),
):
    with _quota(db, user) as (ai_allowed, outcome):
        path = _save_upload(file)
        try:
            with _solver_errors("upload", outcome):
                res = process_exercise_file(path, "Teacher", operation, ai_allowed)
        finally:
            # Data minimization: the photo is only needed to read the exercise. Keeping it
            # would store faces, names and handwriting that nobody uses.
            _remove_files([path])
        outcome["solved"] = res["solved"]
    return _to_response(res, _persist(db, res, user) if res["solved"] else None, mode)


@router.get("/history", response_model=schemas.HistoryPage)
def read_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=100, description="Filtrar por tema o expresión"),
    user: models.User = Depends(current_user),
    db: Session = Depends(database.get_db),
):
    query = db.query(models.Exercise).filter(models.Exercise.user_id == user.id)
    if q:
        like = f"%{q}%"
        query = query.filter(models.Exercise.extracted_latex.ilike(like) |
                             models.Exercise.domain_classification.ilike(like))
    total = query.count()
    rows = query.order_by(models.Exercise.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [{
            "id": r.id,
            "extracted_latex": r.extracted_latex or "",
            "domain_classification": r.domain_classification or "",
            "final_result_latex": r.final_result_latex or "",
            "created_at": r.created_at,
        } for r in rows],
    }


def _get_or_404(db: Session, exercise_id: int, user: models.User) -> models.Exercise:
    ex = db.get(models.Exercise, exercise_id)
    # Someone else's exercise is "not found", not "forbidden": a 403 would confirm that the id exists
    if ex is None or ex.user_id != user.id:
        raise HTTPException(404, "Ejercicio no encontrado.")
    return ex


@router.get("/history/{exercise_id}", response_model=schemas.SolveResponse)
def read_exercise(exercise_id: int, user: models.User = Depends(current_user),
                  db: Session = Depends(database.get_db)):
    ex = _get_or_404(db, exercise_id, user)
    steps = json.loads(ex.solution_steps_json or "[]")
    return {
        "id": ex.id,
        "extracted_latex": ex.extracted_latex or "",
        "domain_classification": ex.domain_classification or "",
        "steps": steps,
        "final_result_latex": ex.final_result_latex or "",
        "graph_data": json.loads(ex.graph_data_json) if ex.graph_data_json else None,
        "solved": True,
        "method": _saved_method(steps),
        "created_at": ex.created_at,
    }


def _saved_method(steps: list[str]) -> str | None:
    """
    The method is not a DB column (adding one needs a migration): it is recovered from the
    labels the pipeline writes into the saved steps, so a history entry solved by the AI
    keeps its warning.
    """
    if any(s.startswith(pipeline.AI_LABEL[:20]) for s in steps):
        return "ai"
    if any(s.startswith(pipeline.INTERPRETED_LABEL) for s in steps):
        return "interpreted"
    return None


def _remove_files(paths: list[str | None]):
    for path in paths:
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError as e:
                logger.warning(f"Could not remove {path}: {e}")


@router.delete("/history/{exercise_id}", status_code=204)
def delete_exercise(exercise_id: int, user: models.User = Depends(current_user),
                    db: Session = Depends(database.get_db)):
    ex = _get_or_404(db, exercise_id, user)
    path = ex.original_image_path
    db.delete(ex)
    db.commit()
    # Files are removed only after the commit succeeds, so a failed delete never orphans a row
    _remove_files([path])


@router.delete("/history", status_code=204)
def clear_history(user: models.User = Depends(current_user), db: Session = Depends(database.get_db)):
    mine = db.query(models.Exercise).filter(models.Exercise.user_id == user.id)
    paths = [p for (p,) in mine.with_entities(models.Exercise.original_image_path)
             .filter(models.Exercise.original_image_path.isnot(None))]
    mine.delete(synchronize_session=False)
    db.commit()
    _remove_files(paths)


@router.get("/health", response_model=schemas.HealthResponse)
def health_check():
    return {"status": "ok", "version": API_VERSION, "ocr": ocr_status(), "ai": llm.available()}
