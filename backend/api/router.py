"""
REST API.

Endpoints are plain `def` on purpose: solving is CPU-bound SymPy work, and
FastAPI runs sync endpoints in a thread pool. Inside `async def` it would
block the event loop and freeze every other request while one solves.
"""
import json
import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

import config
import database
import models
import schemas
from ocr.latex_extractor import ocr_status
from pipeline import OCRError, process_exercise_file, solve_latex_expression

router = APIRouter()
logger = logging.getLogger(__name__)

API_VERSION = "1.1.0"
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
        "created_at": exercise.created_at if exercise else None,
    }


def _persist(db: Session, res: dict, image_path: str | None = None) -> models.Exercise | None:
    """Save the solved exercise. A DB failure must not lose the user's solution, so it only logs."""
    try:
        ex = models.Exercise(
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


@router.post("/solve-text", response_model=schemas.SolveResponse)
def solve_from_text(
    latex_expression: str = Form(...),
    mode: schemas.Mode = Form("Teacher"),
    db: Session = Depends(database.get_db),
):
    try:
        res = solve_latex_expression(latex_expression, "Teacher")
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except Exception:
        logger.error("solve-text error", exc_info=True)
        raise HTTPException(500, "Error interno al resolver el ejercicio.") from None
    return _to_response(res, _persist(db, res) if res["solved"] else None, mode)


@router.post("/upload", response_model=schemas.SolveResponse)
def upload_file(
    mode: schemas.Mode = Form("Teacher"),
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
):
    path = _save_upload(file)
    try:
        res = process_exercise_file(path, "Teacher")
    except (OCRError, ValueError) as e:
        os.remove(path)
        raise HTTPException(422, str(e)) from e
    except Exception:
        os.remove(path)
        logger.error("upload error", exc_info=True)
        raise HTTPException(500, "Error interno al procesar el archivo.") from None
    exercise = _persist(db, res, image_path=path) if res["solved"] else None
    if exercise is None:
        os.remove(path)
    return _to_response(res, exercise, mode)


@router.get("/history", response_model=schemas.HistoryPage)
def read_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=100, description="Filtrar por tema o expresión"),
    db: Session = Depends(database.get_db),
):
    query = db.query(models.Exercise)
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


def _get_or_404(db: Session, exercise_id: int) -> models.Exercise:
    ex = db.get(models.Exercise, exercise_id)
    if ex is None:
        raise HTTPException(404, "Ejercicio no encontrado.")
    return ex


@router.get("/history/{exercise_id}", response_model=schemas.SolveResponse)
def read_exercise(exercise_id: int, db: Session = Depends(database.get_db)):
    ex = _get_or_404(db, exercise_id)
    return {
        "id": ex.id,
        "extracted_latex": ex.extracted_latex or "",
        "domain_classification": ex.domain_classification or "",
        "steps": json.loads(ex.solution_steps_json or "[]"),
        "final_result_latex": ex.final_result_latex or "",
        "graph_data": json.loads(ex.graph_data_json) if ex.graph_data_json else None,
        "solved": True,
        "created_at": ex.created_at,
    }


def _remove_files(paths: list[str | None]):
    for path in paths:
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError as e:
                logger.warning(f"Could not remove {path}: {e}")


@router.delete("/history/{exercise_id}", status_code=204)
def delete_exercise(exercise_id: int, db: Session = Depends(database.get_db)):
    ex = _get_or_404(db, exercise_id)
    path = ex.original_image_path
    db.delete(ex)
    db.commit()
    # Files are removed only after the commit succeeds, so a failed delete never orphans a row
    _remove_files([path])


@router.delete("/history", status_code=204)
def clear_history(db: Session = Depends(database.get_db)):
    paths = [p for (p,) in db.query(models.Exercise.original_image_path)
             .filter(models.Exercise.original_image_path.isnot(None))]
    db.query(models.Exercise).delete()
    db.commit()
    _remove_files(paths)


@router.get("/health", response_model=schemas.HealthResponse)
def health_check():
    return {"status": "ok", "version": API_VERSION, "ocr": ocr_status()}
