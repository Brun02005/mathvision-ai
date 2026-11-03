"""
Main pipeline: File/Text → OCR → (intent · classify · solve · explain · graph)

Three tiers, always in this order, and the response says which one answered (`method`):
1. "symbolic":    the exact engine (SymPy) reads and solves it, with independent verification.
2. "interpreted": the AI only rewrites the exercise in the engine's notation (word problems,
                  odd notation, OCR errors); the engine solves and verifies it.
3. "ai":          the AI solves it itself. Labeled in the steps and never marked verified.
"""
import hashlib
import io
import logging
import os

import config
import solver_pool
from classifier import domain_router as dr
from classifier import intent
from engines.math import algebra, calculus, linear_algebra, ode, series, statistics, transform, vectors
from engines.math.common import clean_latex, natural_language_words, unsolved_result
from engines.physics import physics_engine
from explanations import pedagogical_engine
from graphs import generator
from interpreter import llm, natural
from ocr.latex_extractor import extract_latex_from_image
from ocr.preprocessing import load_image
from pdf.parser import render_pdf_pages
from PIL import Image

logger = logging.getLogger(__name__)

MAX_LATEX_LENGTH = 4000  # word problems are longer than formulas

SOLVERS = {
    dr.INTEGRAL: calculus.solve_integral,
    dr.DERIVATIVE: calculus.solve_derivative,
    dr.LIMIT: calculus.solve_limit,
    dr.SERIES: series.solve_series,
    dr.ODE: ode.solve_ode,
    dr.LINEAR_ALGEBRA: linear_algebra.solve_linear_algebra,
    dr.PHYSICS: physics_engine.solve_physics,
    dr.STATISTICS: statistics.solve_statistics,
    dr.VECTORS: vectors.solve_vectors,
}

# Explicit operations (UI selector or a command in the exercise): (domain shown, solver)
OPERATION_SOLVERS = {
    intent.SIMPLIFY: (dr.ALGEBRA, transform.simplify),
    intent.FACTOR: (dr.ALGEBRA, transform.factor),
    intent.EXPAND: (dr.ALGEBRA, transform.expand),
    intent.PARTIAL_FRACTIONS: (dr.ALGEBRA, transform.partial_fractions),
    intent.TAYLOR: (dr.SERIES, transform.taylor),
    intent.DERIVATIVE: (dr.DERIVATIVE, calculus.solve_derivative),
    intent.INTEGRAL: (dr.INTEGRAL, calculus.solve_integral),
    intent.ANALYZE: (dr.FUNCTION, algebra.analyze),
}

WORD_PROBLEM_HINT = ("Para resolver enunciados en palabras hace falta el asistente de IA, que no está disponible "
                     "en este momento. Mientras tanto, escribí la ecuación o la cuenta, por ejemplo `v = d / t, d = 120, t = 2`.")
INTERPRETED_LABEL = "**Cómo entendimos el ejercicio:**"
AI_LIMIT_MESSAGE = ("Este ejercicio necesita el asistente de IA, y ya usaste los de hoy de tu plan. "
                    "Se renuevan mañana, o podés pasarte a Pro para tener más.")
AI_LABEL = ("⚠ **Resuelto con IA.** Este ejercicio no se pudo resolver con el motor de cálculo exacto, así que lo "
            "resolvió un modelo de lenguaje. Puede equivocarse: revisá el resultado.")


class OCRError(ValueError):
    """The file could be read but no math expression was found in it."""


def decode_upload(path: str) -> list[bytes]:
    """
    Image or PDF → up to MAX_PAGES PNG images of bounded size. Runs in a solver worker:
    decoding files sent by strangers is where malformed or malicious files (decompression
    bombs, pathological PDFs) attack, so it gets the worker's time and memory limits
    instead of risking the server process.
    """
    pages = render_pdf_pages(path) if os.path.splitext(path)[1].lower() == ".pdf" else [load_image(path)]
    encoded = []
    for page in pages:
        page.thumbnail((2000, 2000))
        buf = io.BytesIO()
        page.save(buf, format="PNG")
        encoded.append(buf.getvalue())
    return encoded


def _isolated(func, *args):
    if config.SOLVER_WORKERS <= 0:
        return func(*args)
    return solver_pool.get_pool().run(func, *args)


def process_exercise_file(path: str, mode: str = "Teacher", operation: str = intent.AUTO,
                          ai_allowed: bool = True) -> dict:
    """Image or PDF → LaTeX → solution. Decoding runs isolated; the OCR call (network) runs here."""
    latex_expr = ""
    for png in _isolated(decode_upload, path):
        latex_expr = extract_latex_from_image(Image.open(io.BytesIO(png)))
        if latex_expr:
            break

    if not latex_expr or not latex_expr.strip():
        raise OCRError("No se pudo leer ninguna expresión matemática. Probá con una imagen más clara o usá el modo texto.")
    return solve(latex_expr, mode, operation, ai_allowed)


def _validate(latex_expr: str) -> str:
    latex_expr = (latex_expr or "").strip()
    if not latex_expr:
        raise ValueError("La expresión está vacía.")
    if len(latex_expr) > MAX_LATEX_LENGTH:
        raise ValueError(f"La expresión es demasiado larga (máximo {MAX_LATEX_LENGTH} caracteres).")
    return latex_expr


def _engine(text: str, mode: str, operation: str) -> dict:
    """The exact engine, in an isolated worker process with a time limit."""
    return _isolated(solve_latex_expression, text, mode, operation)


def solve(text: str, mode: str = "Teacher", operation: str = intent.AUTO, ai_allowed: bool = True) -> dict:
    """
    Entry point for the API. Runs the three tiers described at the top of the module.
    The AI calls happen here, in the server process: they are network I/O, and the
    engine workers' time limit is meant for CPU-bound math, not for waiting on an API.
    `ai_allowed` is False when the user has no AI quota left today.
    Raises solver_pool.SolverTimeout / SolverBusy / SolverCrashed besides ValueError.
    """
    text = _validate(text)  # reject bad input before taking a worker
    use_ai = ai_allowed and llm.available()
    try:
        result = _engine(text, mode, operation)
    except solver_pool.SolverTimeout:
        if not use_ai:
            raise
        result = None  # too heavy for the engine: go straight to the AI
    if result is not None and result["solved"]:
        return {**result, "method": "symbolic"}
    if not use_ai:
        if llm.available() and not ai_allowed:
            result = {**result, "ai_limit_reached": True,
                      "steps": [*result["steps"], AI_LIMIT_MESSAGE] if mode == "Teacher" else result["steps"]}
        return result

    if result is not None:
        translation = llm.translate(text, operation)
        if translation is not None and translation.kind == "not_math":
            return _not_math(text)
        if translation is not None and translation.latex.strip() and translation.latex.strip() != text:
            try:
                second = _engine(translation.latex, mode, translation.operation)
            except (solver_pool.SolverTimeout, ValueError):
                second = None
            if second is not None and second["solved"]:
                return _interpreted(second, text, translation, mode)

    solution = llm.solve(text)
    if solution is not None:
        return _ai_result(solution, text, mode)
    if result is None:
        raise solver_pool.SolverTimeout()
    return result  # nobody could solve it: say so, never invent


def _interpreted(result: dict, original: str, translation, mode: str) -> dict:
    steps = result["steps"]
    if mode == "Teacher":
        steps = [f"{INTERPRETED_LABEL} {translation.reading}",
                 f"Lo escribimos así para resolverlo: $${translation.latex}$$", *steps]
    return {**result, "extracted_latex": original, "interpretation": translation.latex,
            "steps": steps, "method": "interpreted"}


def _ai_result(solution, original: str, mode: str) -> dict:
    return {
        "extracted_latex": original,
        "domain_classification": solution.topic,
        "symbolic_representation": solution.answer_sympy,
        "steps": [AI_LABEL, *solution.steps] if mode == "Teacher" else [AI_LABEL],
        "final_result_latex": solution.final_latex,
        "graph_data": None,
        "solved": True,
        "verified": None,
        "method": "ai",
        "answer": solution.answer_sympy or None,
    }


def _not_math(original: str) -> dict:
    return {
        "extracted_latex": original, "domain_classification": "Sin ejercicio", "symbolic_representation": "",
        "steps": ["No encontramos un ejercicio de matemática en lo que enviaste. "
                  "Escribí la cuenta, la ecuación o el enunciado del problema."],
        "final_result_latex": r"\text{No es un ejercicio de matemática}", "graph_data": None,
        "solved": False, "verified": None, "method": "ai",
    }


def run_solver(latex_expr: str, operation: str = intent.AUTO) -> tuple[str, dict]:
    """
    Intent → domain → solver. Returns (domain, raw solver result with SymPy objects
    in `answer`). The benchmark calls this directly to compare answers exactly.
    """
    latex_expr = _validate(latex_expr)
    try:
        return _route(latex_expr, operation)
    except ValueError:
        raise  # invalid input: the API answers 422 with the message
    except Exception:
        # A bug in one solver must not become a 500: log it with the input that caused it
        # A hash identifies repeated crashes of the same input without storing the exercise itself
        digest = hashlib.sha256(latex_expr.encode()).hexdigest()[:12]
        logger.exception(f"Solver crashed on input {digest} ({len(latex_expr)} chars, operation={operation})")
        logger.debug(f"Crashing input {digest}: {latex_expr!r}")
        return "Error", unsolved_result(latex_expr, [], "Ocurrió un error interno al resolver este ejercicio.")


def _route(latex_expr: str, operation: str) -> tuple[str, dict]:
    it = intent.detect_intent(latex_expr, operation)
    body = it.body
    if not body:
        raise ValueError("Falta la expresión sobre la que operar.")

    # Taylor and statistics take parameters in words ("en x = 0", "orden 4")
    takes_words = it.operation in (intent.STATISTICS, intent.TAYLOR)
    if not takes_words:
        body = natural.to_math(body)  # "x al cuadrado menos 4 igual a 0" → x^{2} - 4 = 0
    if natural_language_words(clean_latex(body)) and not takes_words:
        return "Enunciado", {"symbolic": body, "final_latex": r"\text{Enunciado en palabras}",
                             "steps": [WORD_PROBLEM_HINT], "show_graph": False, "ok": False}

    if it.operation == intent.STATISTICS:
        return dr.STATISTICS, statistics.solve_statistics(body, it.params.get("stat"))
    if it.operation in OPERATION_SOLVERS:
        domain, solver = OPERATION_SOLVERS[it.operation]
        return domain, solver(body)

    domain = dr.classify_domain(body)
    if it.operation == intent.SOLVE and "=" not in body and domain in (dr.ALGEBRA, dr.TRIG, dr.COMPLEX):
        body += " = 0"  # "resolver x^2 - 4" means x^2 - 4 = 0
        domain = dr.classify_domain(body)
    return domain, SOLVERS.get(domain, algebra.solve_equation)(body)


def solve_latex_expression(latex_expr: str, mode: str = "Teacher", operation: str = intent.AUTO) -> dict:
    """Intent → classify → solve → explain → graph, in the current process and without time limit."""
    latex_expr = _validate(latex_expr)
    domain, solution = run_solver(latex_expr, operation)
    # Exercises are user content: logs keep what was solved and how, not the text itself
    logger.info(f"Solved: domain={domain} operation={operation} chars={len(latex_expr)} ok={solution.get('ok', True)}")
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
        "verified": solution.get("verified") if ok else None,
        # Machine-readable answer (SymPy srepr) for the AI benchmark; the API does not expose it
        "answer": _serialize(solution.get("answer")) if ok else None,
    }


def _serialize(answer):
    import sympy as sp
    if answer is None or isinstance(answer, str):
        return answer
    try:
        return sp.srepr(answer)
    except Exception:
        return repr(answer)
