"""
Mathematical (not textual) comparison of a solver answer with the expected one:
x = 1/2 and x = 0.5 are the same answer, and so are ln|x| and ln|x| + 3 as antiderivatives.
"""
import re

import sympy as sp

from engines.math.common import same_function

x = sp.Symbol("x")


def _expr_equal(a, b) -> bool:
    try:
        a, b = sp.sympify(a), sp.sympify(b)
    except (sp.SympifyError, TypeError):
        return False
    if a == b:
        return True
    try:
        diff = sp.simplify(a - b)
        if diff == 0:
            return True
        if diff.is_number:
            return abs(complex(sp.N(diff, 20))) < 1e-9
    except Exception:
        pass
    free = (a.free_symbols | b.free_symbols)
    if len(free) == 1:
        return bool(same_function(a, b, next(iter(free))))
    return False


def _set_equal(a, b) -> bool:
    if isinstance(a, sp.FiniteSet) and isinstance(b, sp.FiniteSet):
        if len(a) != len(b):
            return False
        return all(any(_expr_equal(e, f) for f in a) for e in b)
    if a == b:
        return True
    try:
        return sp.Complement(a, b) == sp.S.EmptySet and sp.Complement(b, a) == sp.S.EmptySet
    except Exception:
        return False


def _as_matrix(v):
    if isinstance(v, (tuple, list)) and v and not isinstance(v[0], dict):
        return sp.ImmutableMatrix(v)
    return v


_SAFE_TEXT = re.compile(r"^[\w\s+\-*/^().,{}\[\]:'=<>]*$")


def contains_answer(answer, expected, kind: str = "value", var=x) -> bool:
    """
    For the AI benchmark: `answer` may come as text (SymPy srepr from the engine, or SymPy
    syntax written by the model). A system answer {x: 17, y: 13} contains 17.
    """
    if answer is None:
        return False
    if isinstance(answer, str):
        # sympify evaluates its input: never feed it model output that is not plain math
        if "__" in answer or not _SAFE_TEXT.match(answer):
            return False
        try:
            answer = sp.sympify(answer)
        except (sp.SympifyError, SyntaxError, TypeError):
            return False
    if kind == "antiderivative":
        return equivalent(answer, expected, kind, var)
    if isinstance(answer, sp.Set) and isinstance(expected, sp.Set):
        return equivalent(answer, expected)
    if isinstance(answer, dict):
        candidates = list(answer.values())
    elif isinstance(answer, (list, tuple, sp.FiniteSet)):
        candidates = [v for item in answer for v in (item.values() if isinstance(item, dict) else [item])]
    elif isinstance(answer, sp.Equality):
        candidates = [answer.rhs]
    else:
        candidates = [answer]
    return any(_expr_equal(c, expected) for c in candidates if isinstance(c, (sp.Basic, int, float)))


def equivalent(actual, expected, kind: str = "value", var=x) -> bool:
    if kind == "antiderivative":
        # Antiderivatives may differ by a constant: compare derivatives, over the reals
        # (d/dx ln|x| is only 1/x for a real x)
        real = sp.Symbol(var.name, real=True)
        f, g = (sp.sympify(e).xreplace({var: real}) for e in (actual, expected))
        return _expr_equal(sp.diff(f, real).xreplace({real: var}), sp.diff(g, real).xreplace({real: var}))
    if kind == "ode":
        # General solutions: the arbitrary constants may come in another order
        c1, c2 = sp.symbols("C1 C2")
        actual = sp.sympify(actual)
        return _expr_equal(actual, expected) or _expr_equal(actual.subs({c1: c2, c2: c1}, simultaneous=True), expected)
    if kind == "factored":
        return _expr_equal(actual, expected) and not isinstance(actual, sp.Add)
    if kind == "expanded":
        return _expr_equal(actual, expected) and sp.expand(actual) == actual
    if kind == "sum_of_fractions":
        return _expr_equal(actual, expected) and isinstance(actual, sp.Add)

    if isinstance(expected, str):
        return actual == expected
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and equivalent(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):  # several solutions of a system, in any order
        return (isinstance(actual, list) and len(actual) == len(expected)
                and all(any(equivalent(a, e) for a in actual) for e in expected))
    if isinstance(expected, sp.Set):
        return isinstance(actual, sp.Set) and _set_equal(actual, expected)

    expected, actual = _as_matrix(expected), _as_matrix(actual)
    if isinstance(expected, sp.MatrixBase):
        if not isinstance(actual, sp.MatrixBase):
            return False
        if actual.shape != expected.shape:
            actual = actual.reshape(*expected.shape) if len(actual) == len(expected) else actual
        return actual.shape == expected.shape and all(_expr_equal(a, e) for a, e in zip(actual, expected, strict=True))
    if isinstance(actual, (str, dict, list, sp.Set, sp.MatrixBase)) or actual is None:
        return False
    return _expr_equal(actual, expected)
