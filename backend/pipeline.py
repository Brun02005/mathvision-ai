"""
Main pipeline: File/Text → OCR → Classify → Solve → Explain → Graph
"""
import logging
import os

from classifier import domain_router as dr
from engines.math import algebra, calculus, linear_algebra, ode, series
from engines.physics import physics_engine
from explanations import pedagogical_engine
from graphs import generator
from ocr.latex_extractor import extract_latex_from_image
from ocr.preprocessing import load_image
from pdf.parser import render_pdf_pages

logger = logging.getLogger(__name__)

MAX_LATEX_LENGTH = 2000

SOLVERS = {
    dr.INTEGRAL: calculus.solve_integral,
    dr.DERIVATIVE: calculus.solve_derivative,
    dr.LIMIT: calculus.solve_limit,
    dr.SERIES: series.solve_series,
    dr.ODE: ode.solve_ode,
    dr.LINEAR_ALGEBRA: linear_algebra.solve_linear_algebra,
    dr.PHYSICS: physics_engine.solve_physics,
}


class OCRError(ValueError):
    """The file could be read but no math expression was found in it."""


def process_exercise_file(path: str, mode: str = "Teacher") -> dict:
    """Image or PDF → LaTeX → solution."""
    if os.path.splitext(path)[1].lower() == ".pdf":
        latex_expr = ""
        for page in render_pdf_pages(path):
            latex_expr = extract_latex_from_image(page)
            if latex_expr:
                break
    else:
        latex_expr = extract_latex_from_image(load_image(path))

    if not latex_expr or not latex_expr.strip():
        raise OCRError("No se pudo leer ninguna expresión matemática. Probá con una imagen más clara o usá el modo texto.")
    return solve_latex_expression(latex_expr, mode)


def solve_latex_expression(latex_expr: str, mode: str = "Teacher") -> dict:
    latex_expr = (latex_expr or "").strip()
    if not latex_expr:
        raise ValueError("La expresión está vacía.")
    if len(latex_expr) > MAX_LATEX_LENGTH:
        raise ValueError(f"La expresión es demasiado larga (máximo {MAX_LATEX_LENGTH} caracteres).")

    domain = dr.classify_domain(latex_expr)
    logger.info(f"Domain: {domain} | Expression: {latex_expr[:80]}")

    solver = SOLVERS.get(domain, algebra.solve_equation)
    solution = solver(latex_expr)
    ok = solution.get("ok", True)

    raw_steps = solution.get("steps", [])
    if mode != "Teacher":
        steps = []
    elif ok:
        steps = pedagogical_engine.enhance_explanation(domain, raw_steps)
    else:
        steps = raw_steps

    graph_data = None
    if ok and solution.get("show_graph") and solution.get("graph"):
        try:
            graph_data = generator.generate_graph(solution["graph"])
        except Exception as e:
            logger.warning(f"Graph generation failed: {e}")

    return {
        "extracted_latex": latex_expr,
        "domain_classification": domain,
        "symbolic_representation": solution.get("symbolic", ""),
        "steps": steps,
        "final_result_latex": solution.get("final_latex", ""),
        "graph_data": graph_data,
        "solved": ok,
    }
