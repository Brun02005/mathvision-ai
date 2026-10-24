from sqlalchemy import Column, Integer, String, Text, DateTime
from database import Base
import datetime

class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    original_image_path = Column(String, nullable=True)
    extracted_latex = Column(Text, nullable=False)
    domain_classification = Column(String, nullable=True) # e.g. "Calculus", "Physics"
    symbolic_representation = Column(Text, nullable=True)
    solution_steps_json = Column(Text, nullable=True) # JSON containing steps in Spanish
    final_result_latex = Column(Text, nullable=True)
    graph_data_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
