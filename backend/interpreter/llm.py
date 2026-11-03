"""
AI layer (Gemini) for exercises the symbolic engine cannot read on its own:
word problems, unusual notation, badly typed or badly photographed exercises.

Two roles, always tried in this order by the pipeline:
1. translate(): rewrite the exercise in the solver's notation, WITHOUT solving it.
   The symbolic engine then solves and verifies it, so the answer is still exact.
2. solve(): last resort, the model solves it itself. The result is labeled
   "resuelto con IA" and never gets the "verified" badge: a model can be
   confidently wrong, and checking its answer against its own formalization
   would be circular.

Model output is untrusted data: it is validated (schema, enums, sizes) before
use, and only ever rendered as escaped text / KaTeX with trust disabled.
"""
import json
import logging
import os
import threading
from collections import OrderedDict
from functools import wraps

from pydantic import BaseModel, Field, ValidationError

from classifier.intent import OPERATIONS
from interpreter import metering

logger = logging.getLogger(__name__)

TRANSLATE_TIMEOUT_MS = 25_000
SOLVE_TIMEOUT_MS = 45_000
MAX_STEPS = 30
MAX_STEP_CHARS = 1500

NOTATION = r"""Notation the solver understands (LaTeX):
- Equations: x^2 - 5x + 6 = 0 · systems separated by ';': 2x + 3y = 6; x - y = 1
- Inequalities: \frac{x-1}{x+2} \geq 0 · double: -1 < 2x + 3 \leq 5
- Integrals: \int_{a}^{b} f(x)\,dx · derivatives: \frac{d}{dx}(f(x)) · partial: \frac{\partial}{\partial x}(f)
- Limits: \lim_{x \to a} f(x) · series: \sum_{n=1}^{\infty} a_n
- ODEs: y'' + y = 0, y(0) = 1, y'(0) = 0 · implicit derivative: x^2 + y^2 = 25, \frac{dy}{dx}
- Matrices: \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix} · vectors: (1, 2, 3) \times (4, 5, 6)
- Statistics: 2, 4, 4, 5, 7 (list of numbers) · complex numbers use i
- Physics / formulas with data: formula first, then the data: v = \frac{d}{t}, d = 120, t = 2
- \log without base is base 10, \ln is natural. Use explicit multiplication \cdot when in doubt.
Operations (field "operation"): """ + ", ".join(OPERATIONS)

TRANSLATE_PROMPT = """You translate math exercises (any language, any format: words, plain text,
badly written LaTeX, OCR output with errors) into the notation of a symbolic solver.
Do NOT solve the exercise and do NOT include the answer: only formalize it.
For word problems, define the unknowns with single letters and write the equations
(or the formula plus data) that model the problem.
If the text has OCR errors, write the most plausible intended exercise.
If several exercises are present, take the first one.
If it is not a math exercise, set kind to "not_math".

""" + NOTATION

SOLVE_PROMPT = """You are a university math teacher from Argentina. Solve the exercise step by step,
in Spanish (neutral, using "vos" is fine). Formatting rules for each step:
- inline math between single dollars $...$, displayed math between $$...$$
- **bold** for key ideas; no HTML, no markdown headings, no tables
Keep each step short. Put the final answer, in LaTeX without dollars, in final_latex.
In answer_sympy write the final answer in SymPy syntax when it is a number, expression,
set of solutions or similar (empty string otherwise).
If the exercise is ambiguous or illegible, state the most plausible reading in the first step."""


class Translation(BaseModel):
    kind: str = Field(description='"math" or "not_math"')
    latex: str = Field(description="The exercise in the solver notation")
    operation: str = Field(description="One of the solver operations")
    reading: str = Field(description="One short sentence in Spanish: how the exercise was understood")


class AISolution(BaseModel):
    topic: str = Field(description="Topic in Spanish, e.g. 'Probabilidad', 'Geometría'")
    steps: list[str]
    final_latex: str
    answer_sympy: str = ""


def available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def _model() -> str:
    from ocr.latex_extractor import DEFAULT_GEMINI_MODEL
    return os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)


def _ask(prompt: str, content: str, schema: type[BaseModel], timeout_ms: int):
    """One structured call. Returns a validated `schema` instance, or None on any failure."""
    from google.genai import types

    from ocr.latex_extractor import _get_gemini_client
    try:
        response = _get_gemini_client().models.generate_content(
            model=_model(),
            contents=[content],
            config=types.GenerateContentConfig(
                system_instruction=prompt,
                temperature=0,
                response_mime_type="application/json",
                response_schema=schema,
                http_options=types.HttpOptions(timeout=timeout_ms),
            ),
        )
        metering.record(response, assistant=True)  # tokens are paid even if the answer is unusable
        data = response.parsed if isinstance(response.parsed, schema) else schema(**json.loads(response.text))
        return data
    except (ValidationError, json.JSONDecodeError, TypeError) as e:
        logger.warning(f"AI returned an invalid {schema.__name__}: {e}")
    except Exception as e:
        logger.warning(f"AI call failed ({schema.__name__}): {e}")
    return None


def _cache_successes(maxsize: int = 512):
    """
    LRU cache that only stores successful results: popular homework is asked many times
    and each call costs money, but a transient failure (timeout, quota) must not be
    remembered as the answer. Thread-safe, since endpoints run in a thread pool.
    """
    def decorator(fn):
        cache, lock = OrderedDict(), threading.Lock()

        @wraps(fn)
        def wrapper(*args):
            with lock:
                if args in cache:
                    cache.move_to_end(args)
                    return cache[args]
            result = fn(*args)
            if result is not None:
                with lock:
                    cache[args] = result
                    if len(cache) > maxsize:
                        cache.popitem(last=False)
            return result
        wrapper.cache_clear = cache.clear
        return wrapper
    return decorator


@_cache_successes()
def translate(text: str, operation: str = "auto") -> Translation | None:
    hint = "" if operation == "auto" else f"\nThe user asked for the operation: {operation}."
    t = _ask(TRANSLATE_PROMPT, f"Exercise:\n{text}{hint}", Translation, TRANSLATE_TIMEOUT_MS)
    if t is None:
        return None
    if t.kind not in ("math", "not_math") or t.operation not in OPERATIONS or len(t.latex) > 2000:
        logger.warning(f"AI translation rejected: {t!r}")
        return None
    t.reading = t.reading[:300]
    return t


@_cache_successes()
def solve(text: str) -> AISolution | None:
    s = _ask(SOLVE_PROMPT, f"Exercise:\n{text}", AISolution, SOLVE_TIMEOUT_MS)
    if s is None or not s.steps or not s.final_latex.strip():
        return None
    s.steps = [step[:MAX_STEP_CHARS] for step in s.steps[:MAX_STEPS]]
    s.final_latex = s.final_latex[:MAX_STEP_CHARS]
    s.topic = s.topic[:60] or "Matemática"
    s.answer_sympy = s.answer_sympy[:500]
    return s
