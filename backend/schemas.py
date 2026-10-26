from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel

Mode = Literal["Teacher", "Exam"]


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
    created_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    ocr: dict[str, bool]
