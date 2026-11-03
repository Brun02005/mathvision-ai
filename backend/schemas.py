from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel

Mode = Literal["Teacher", "Exam"]
# Kept in sync with classifier.intent.OPERATIONS (checked by a test)
Operation = Literal["auto", "solve", "simplify", "factor", "expand", "partial_fractions",
                    "derivative", "integral", "taylor", "analyze", "statistics"]


class HistoryItem(BaseModel):
    id: int
    extracted_latex: str
    domain_classification: str
    final_result_latex: str
    created_at: datetime


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int


class SolveResponse(BaseModel):
    id: Optional[int] = None
    extracted_latex: str
    domain_classification: str
    steps: list[str]
    final_result_latex: str
    graph_data: Optional[dict[str, Any]] = None
    solved: bool = True
    # True: the result was checked independently (substitution, derivative, numeric evaluation)
    verified: Optional[bool] = None
    # Who solved it: "symbolic" (exact engine), "interpreted" (AI translated, engine solved), "ai"
    method: Optional[Literal["symbolic", "interpreted", "ai"]] = None
    # How the AI rewrote the exercise for the engine (method "interpreted")
    interpretation: Optional[str] = None
    created_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    ocr: dict[str, bool]
    # AI assistant for word problems and exercises the exact engine cannot read
    ai: bool = False
