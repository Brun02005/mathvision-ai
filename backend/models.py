import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime

from database import Base


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    original_image_path = Column(String, nullable=True)
    extracted_latex = Column(Text, nullable=False)
    domain_classification = Column(String, nullable=True)  # e.g. "Cálculo Integral", "Física"
    symbolic_representation = Column(Text, nullable=True)
    solution_steps_json = Column(Text, nullable=True)  # JSON list of steps in Spanish
    final_result_latex = Column(Text, nullable=True)
    graph_data_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
