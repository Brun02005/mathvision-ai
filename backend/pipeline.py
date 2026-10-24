import json
import logging
from ocr.preprocessing import preprocess_image_for_ocr
from ocr.latex_extractor import extract_latex_from_image
from classifier.domain_router import classify_domain
from engines.math import calculus, algebra
from explanations import pedagogical_engine
from graphs import generator

logger = logging.getLogger(__name__)


def process_exercise_image(image_path: str) -> dict:
    """Main pipeline: Image → OCR → Classify → Solve → Explain → Graph"""
    # 1. Preprocess image
    pil_image = preprocess_image_for_ocr(image_path)

    # 2. Extract LaTeX
    latex_expr = extract_latex_from_image(pil_image)
    if not latex_expr or latex_expr.strip() == "":
        raise ValueError("El OCR no pudo extraer texto. Intenta con imagen más clara o usá modo texto.")

    return _solve_latex(latex_expr.strip(), mode="Teacher")


def solve_latex_expression(latex_expr: str, mode: str = "Teacher") -> dict:
    """Solve a LaTeX expression given as text."""
    return _solve_latex(latex_expr.strip(), mode)


def _solve_latex(latex_expr: str, mode: str) -> dict:
    # 3. Classify
    domain = classify_domain(latex_expr)
    logger.info(f"Domain: {domain} | Expression: {latex_expr[:60]}")

    # 4. Solve
    from engines.physics import physics_engine
    if domain == "Cálculo Integral":
        solution = calculus.solve_integral(latex_expr)
    elif domain == "Cálculo Diferencial":
        solution = calculus.solve_derivative(latex_expr)
    elif domain in ["Física", "Cinemática", "Dinámica"]:
        solution = physics_engine.solve_physics(latex_expr, sub_domain=domain)
    else:
        solution = algebra.solve_equation(latex_expr)

    raw_steps = solution.get("steps", [])

    # 5. Enhance explanations (Teacher mode only)
    if mode == "Teacher":
        enhanced_steps = pedagogical_engine.enhance_explanation(domain, raw_steps)
    else:
        enhanced_steps = []

    # 6. Graph — only when the solver says it makes sense
    graph_data = None
    should_graph = solution.get("show_graph", False)
    if should_graph:
        graph_data = generator.generate_function_graph_data(latex_expr)

    return {
        "extracted_latex": latex_expr,
        "domain_classification": domain,
        "symbolic_representation": solution.get("symbolic", ""),
        "steps": enhanced_steps,
        "final_result_latex": solution.get("final_latex", ""),
        "graph_data": graph_data,
    }
