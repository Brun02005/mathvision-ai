"""
Heuristics-based domain classifier. The order of the checks matters: more
specific structures (integrals, ODEs, matrices) are tested before generic ones.
"""
import re

from engines.math.calculus import implicit_request
from engines.math.vectors import TUPLE
from engines.physics.physics_engine import looks_like_physics

INTEGRAL = "Cálculo Integral"
DERIVATIVE = "Cálculo Diferencial"
LIMIT = "Límites"
ODE = "Ecuaciones Diferenciales"
SERIES = "Series y Sucesiones"
LINEAR_ALGEBRA = "Álgebra Lineal"
PHYSICS = "Física"
TRIG_EQUATION = "Ecuaciones Trigonométricas"
TRIG = "Trigonometría"
SYSTEM = "Sistemas de Ecuaciones"
INEQUALITY = "Inecuaciones"
FUNCTION = "Análisis de Funciones"
ALGEBRA = "Álgebra"
ARITHMETIC = "Aritmética"
COMPLEX = "Números Complejos"
STATISTICS = "Estadística"
VECTORS = "Vectores"

DOMAINS = [ARITHMETIC, ALGEBRA, INEQUALITY, SYSTEM, FUNCTION, TRIG, TRIG_EQUATION, COMPLEX,
           LIMIT, DERIVATIVE, INTEGRAL, SERIES, ODE, LINEAR_ALGEBRA, VECTORS, STATISTICS, PHYSICS]

_NUMBER_LIST = re.compile(r"^\s*-?\d+(?:[.,]\d+)?(?:\s*[,;]\s*-?\d+(?:[.,]\d+)?){2,}\s*$")
_NUMERIC_TUPLE = re.compile(r"(?:\\langle|\()\s*-?[\d.]+(?:\s*,\s*-?[\d.]+){1,3}\s*(?:\\rangle|\))")

_DERIV_OP = re.compile(r"\\frac\{d(\^\{?\d+\}?)?\}\{d[a-z]|d\s*/\s*d[a-z]|\\frac\{\\partial")
# dy/dx or d^2y/dx^2 → derivative of an unknown function (ODE when there is an '=')
_LEIBNIZ_UNKNOWN = re.compile(r"\\frac\{d(\^\{?\d+\}?)?\s*[a-z]\}\{d[a-z]")
_PRIME = re.compile(r"[a-z]\s*('|\^\{?\\prime)")
_FUNC_PRIME_DEF = re.compile(r"^\s*[fgh]\s*'+\s*\(\s*[a-z]\s*\)\s*(=|$)")
_FUNC_DEF = re.compile(r"^\s*[fghy]\s*(\(\s*[a-z]\s*\))?\s*=")
_MATRIX = re.compile(r"\\begin\{[pbBvV]?matrix\}|\\det\b")
# (?![a-zA-Z]) so that \left is not read as \le
_INEQ = re.compile(r"\\(?:leq?|geq?|leqslant|geqslant|lt|gt)(?![a-zA-Z])|<|>|≤|≥")
_TRIG = re.compile(r"\\(sin|cos|tan|cot|sec|csc)\b")
_VARS = re.compile(r"(?<!\\)(?<![a-zA-Z])[a-zA-Z](?![a-zA-Z])")


def _has_variables(s: str) -> bool:
    stripped = re.sub(r"\\[a-zA-Z]+", " ", s)
    return bool(_VARS.search(stripped))


def classify_domain(latex_expression: str) -> str:
    s = latex_expression.strip()

    if "\\int" in s:
        return INTEGRAL
    if _MATRIX.search(s):
        return LINEAR_ALGEBRA
    if _NUMBER_LIST.match(s):
        return STATISTICS
    if _NUMERIC_TUPLE.search(s) and "=" not in s and len(TUPLE.findall(s)) <= 2:
        return VECTORS
    if "\\sum" in s or "\\prod" in s:
        return SERIES
    if "\\lim" in s:
        return LIMIT

    # Derivatives: f'(x) = ... is "differentiate this", y' = 2y is an ODE,
    # "x^2 + y^2 = 25, dy/dx" is implicit differentiation
    if implicit_request(s):
        return DERIVATIVE
    if _FUNC_PRIME_DEF.match(s):
        return DERIVATIVE
    if _LEIBNIZ_UNKNOWN.search(s) and "=" in s:
        return ODE
    if _PRIME.search(s) and "=" in s:
        return ODE
    if _DERIV_OP.search(s):
        return DERIVATIVE

    if looks_like_physics(s):
        return PHYSICS

    eq_count = s.count("=")
    if eq_count > 1 and re.search(r"[,;]|\\\\|\\begin\{cases\}", s):
        return SYSTEM
    if _INEQ.search(s):
        return INEQUALITY
    if _FUNC_DEF.match(s):
        return FUNCTION

    if _TRIG.search(s):
        return TRIG_EQUATION if "=" in s else TRIG

    if not _has_variables(s):
        return ARITHMETIC
    if "=" not in s and _only_imaginary_unit(s):
        return COMPLEX
    return ALGEBRA


def _only_imaginary_unit(s: str) -> bool:
    stripped = re.sub(r"\\[a-zA-Z]+", " ", s)
    return set(_VARS.findall(stripped)) == {"i"}
