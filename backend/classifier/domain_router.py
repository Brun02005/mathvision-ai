"""
Heuristics-based domain classifier. The order of the checks matters: more
specific structures (integrals, ODEs, matrices) are tested before generic ones.
"""
import re

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

DOMAINS = [ARITHMETIC, ALGEBRA, INEQUALITY, SYSTEM, FUNCTION, TRIG, TRIG_EQUATION,
           LIMIT, DERIVATIVE, INTEGRAL, SERIES, ODE, LINEAR_ALGEBRA, PHYSICS]

_DERIV_OP = re.compile(r"\\frac\{d(\^\{?\d+\}?)?\}\{d[a-z]|d\s*/\s*d[a-z]|\\frac\{\\partial")
# dy/dx or d^2y/dx^2 → derivative of an unknown function (ODE when there is an '=')
_LEIBNIZ_UNKNOWN = re.compile(r"\\frac\{d(\^\{?\d+\}?)?\s*[a-z]\}\{d[a-z]")
_PRIME = re.compile(r"[a-z]\s*('|\^\{?\\prime)")
_FUNC_PRIME_DEF = re.compile(r"^\s*[fgh]\s*'+\s*\(\s*[a-z]\s*\)\s*(=|$)")
_FUNC_DEF = re.compile(r"^\s*[fghy]\s*(\(\s*[a-z]\s*\))?\s*=")
_MATRIX = re.compile(r"\\begin\{[pbBvV]?matrix\}|\\det\b")
_INEQ = re.compile(r"\\leq?|\\geq?|\\le\b|\\ge\b|<|>|≤|≥")
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
    if "\\sum" in s or "\\prod" in s:
        return SERIES
    if "\\lim" in s:
        return LIMIT

    # Derivatives: f'(x) = ... is "differentiate this", y' = 2y is an ODE
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
    return ALGEBRA
