"""
Accuracy benchmark: runs the golden set of exercises (cases.py) through the
solver and compares each answer mathematically with the expected one.

    python -m benchmark            # report per topic
    python -m benchmark -v         # also list every failure
"""
import time
from dataclasses import dataclass

from benchmark.cases import CASES, Case
from benchmark.cases_independent import CASES as INDEPENDENT_CASES
from benchmark.compare import equivalent

# cases.py (written with the solver) + cases_independent.py (written by a reviewer who never saw it)
ALL_CASES = CASES + INDEPENDENT_CASES


@dataclass
class Outcome:
    case: Case
    passed: bool
    detail: str
    seconds: float
    verified: bool | None = None


def run_case(case: Case) -> Outcome:
    from pipeline import run_solver

    start = time.monotonic()
    try:
        _, result = run_solver(case.latex, case.operation)
    except Exception as e:  # a crash is a failure, not a reason to stop the benchmark
        if case.kind == "rejected" and isinstance(e, ValueError):
            return Outcome(case, True, "rechazado", time.monotonic() - start)
        return Outcome(case, False, f"excepción {type(e).__name__}: {e}", time.monotonic() - start)
    elapsed = time.monotonic() - start

    solved = result.get("ok", True)
    if case.kind == "rejected":
        return Outcome(case, not solved, "rechazado" if not solved else f"inventó: {result.get('final_latex')}", elapsed)
    if not solved:
        return Outcome(case, False, f"no resuelto: {result.get('final_latex')}", elapsed)
    answer = result.get("answer")
    passed = answer is not None and equivalent(answer, case.expected, case.kind)
    detail = "ok" if passed else f"esperado {case.expected!r}, obtenido {answer!r}"
    return Outcome(case, passed, detail, elapsed, result.get("verified"))


def run_all(cases=ALL_CASES) -> list[Outcome]:
    return [run_case(c) for c in cases]
