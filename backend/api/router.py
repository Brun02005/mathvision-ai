from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import database, models
import shutil, os, json, logging

router = APIRouter()
os.makedirs("temp", exist_ok=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _to_response(res: dict) -> dict:
    """Serialize pipeline result → clean JSON-safe dict."""
    return {
        "extracted_latex":       res.get("extracted_latex", ""),
        "domain_classification": res.get("domain_classification", ""),
        "solution_steps_json":   json.dumps(res.get("steps", []),     ensure_ascii=False),
        "final_result_latex":    res.get("final_result_latex", ""),
        "graph_data_json":       json.dumps(res.get("graph_data"),     ensure_ascii=False) if res.get("graph_data") else None,
    }


def _persist(db, res: dict, image_path: str = None):
    try:
        ex = models.Exercise(
            original_image_path=image_path,
            extracted_latex=res["extracted_latex"],
            domain_classification=res["domain_classification"],
            symbolic_representation=res.get("symbolic_representation", ""),
            solution_steps_json=json.dumps(res.get("steps", []), ensure_ascii=False),
            final_result_latex=res["final_result_latex"],
            graph_data_json=json.dumps(res.get("graph_data"), ensure_ascii=False) if res.get("graph_data") else None,
        )
        db.add(ex)
        db.commit()
    except Exception as e:
        logger.warning(f"DB persist skipped: {e}")


@router.post("/solve-text")
async def solve_from_text(
    latex_expression: str = Form(...),
    mode: str = Form("Teacher"),
    db: Session = Depends(database.get_db),
):
    try:
        from pipeline import solve_latex_expression
        res = solve_latex_expression(latex_expression.strip(), mode)
        _persist(db, res)
        return JSONResponse(content=_to_response(res))
    except Exception as e:
        logger.error("solve-text error", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_file(
    mode: str = Form("Teacher"),
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
):
    file_location = f"temp/{file.filename}"
    with open(file_location, "wb+") as f:
        shutil.copyfileobj(file.file, f)

    try:
        from pipeline import process_exercise_image
        res = process_exercise_image(file_location)
        if mode == "Exam":
            res["steps"] = []
        _persist(db, res, image_path=file_location)
        return JSONResponse(content=_to_response(res))
    except Exception as e:
        logger.error("upload error", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
def read_history(skip: int = 0, limit: int = 20, db: Session = Depends(database.get_db)):
    rows = db.query(models.Exercise).order_by(models.Exercise.created_at.desc()).offset(skip).limit(limit).all()
    return JSONResponse(content=[{
        "id": r.id,
        "extracted_latex": r.extracted_latex or "",
        "domain_classification": r.domain_classification or "",
        "final_result_latex": r.final_result_latex or "",
        "created_at": str(r.created_at),
    } for r in rows])


@router.get("/health")
def health_check():
    return {"status": "ok"}
