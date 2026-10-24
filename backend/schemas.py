from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class ExerciseBase(BaseModel):
    extracted_latex: str
    domain_classification: Optional[str] = None
    symbolic_representation: Optional[str] = None

class ExerciseCreate(ExerciseBase):
    pass

class ExerciseResponse(ExerciseBase):
    id: int
    solution_steps_json: Optional[str] = None
    final_result_latex: Optional[str] = None
    graph_data_json: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class SolveRequest(BaseModel):
    latex_expression: str
    mode: str = "Teacher" # "Teacher" or "Exam"
