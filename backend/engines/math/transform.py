"""
Algebraic transformations: simplify, factor, expand, partial fractions and
Taylor polynomials. Every transformation checks that its output is equivalent
to the input before reporting it as verified.
"""
import logging
import re

import sympy as sp

from engines.math.common import clean_latex, error_result, parse_math, pick_variable, same_function

logger = logging.getLogger(__name__)

SEP = r",\; "


def _parse_expression(latex_expr: str, example: str):
    expr = parse_math(latex_expr)
    if expr is None or not isinstance(expr, sp.Expr):
        return None, error_result(latex_expr, f"Ejemplo: `{example}`")
    return expr, None


def _equivalent(a, b, var) -> bool | None:
    try:
        if sp.simplify(sp.expand(a - b)) == 0:
            return True
    except Exception:
        pass
    return same_function(a, b, var) if var is not None else None


def _excluded_points(expr, var) -> list:
    """Zeros of the denominators of the ORIGINAL expression: simplifying can hide them."""
    _, den = sp.fraction(sp.together(expr))
    if not den.has(var):
        return []
    try:
        zeros = sp.solveset(den, var, sp.S.Reals)
        return sorted(zeros, key=float) if isinstance(zeros, sp.FiniteSet) else []
    except Exception:
        return []


def _graph(expr, var):
    return {"var": var, "curves": [{"expr": expr, "label": "f(x)"}]} if expr.free_symbols == {var} else None


def _result(expr, answer, final, steps, verified, graph=None):
    return {"symbolic": str(expr), "final_latex": final, "steps": steps, "answer": answer,
            "verified": verified, "show_graph": graph is not None, "graph": graph}


# ── Simplify ─────────────────────────────────────────────────────────────────

def _simplest_form(expr):
    """
    Simplify over the reals (a calculator user means ln(e^x) = x, √(x²) = |x|) and try
    the Pythagorean identity in both directions, which simplify() alone often misses:
    sin²x / (1 - cos x) → 1 + cos x.
    """
    reals = {s: sp.Symbol(s.name, real=True) for s in expr.free_symbols}
    back = {v: k for k, v in reals.items()}
    e = expr.xreplace(reals)
    candidates = [sp.simplify(e)]
    if e.has(sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc):
        candidates.append(sp.trigsimp(e))
        for v in reals.values():
            rewritten = sp.expand_trig(e.rewrite(sp.cos) if e.has(sp.tan, sp.cot, sp.sec, sp.csc) else e)
            candidates.append(sp.factor(sp.cancel(rewritten.subs(sp.sin(v) ** 2, 1 - sp.cos(v) ** 2))))
            candidates.append(sp.factor(sp.cancel(rewritten.subs(sp.cos(v) ** 2, 1 - sp.sin(v) ** 2))))
    best = min(candidates, key=sp.count_ops)
    return best.xreplace(back)


def simplify(latex_expr: str) -> dict:
    expr, err = _parse_expression(latex_expr, r"\frac{x^2 - 1}{x + 1}")
    if err:
        return err
    var = pick_variable(expr)
    steps = [f"Tenemos la expresión: $${sp.latex(expr)}$$"]

    simp = _simplest_form(expr)
    if expr.has(sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc):
        steps.append(r"Usamos identidades trigonométricas, como $\sin^2 x + \cos^2 x = 1$, para reducir la expresión.")
    num, den = sp.fraction(sp.together(expr))
    if den.has(var):
        steps.append(f"Factorizamos numerador y denominador: $$\\frac{{{sp.latex(sp.factor(num))}}}{{{sp.latex(sp.factor(den))}}}$$")
        steps.append("Cancelamos los factores comunes.")

    steps.append(f"**Forma simplificada:** $${sp.latex(simp)}$$")
    excluded = _excluded_points(expr, var)
    final = sp.latex(simp)
    if excluded:
        cond = SEP.join(f"{sp.latex(var)} \\neq {sp.latex(p)}" for p in excluded)
        steps.append(f"La igualdad vale donde la expresión original está definida: ${cond}$.")
        final += f", \\quad {cond}"

    if simp.free_symbols:
        fact, expd = sp.factor(simp), sp.expand(simp)
        if fact != simp:
            steps.append(f"Forma factorizada: $${sp.latex(fact)}$$")
        if expd != simp and expd != fact:
            steps.append(f"Forma desarrollada: $${sp.latex(expd)}$$")

    verified = _equivalent(expr, simp, var)
    return _result(expr, simp, final, steps, verified, _graph(simp, var))


# ── Factor ───────────────────────────────────────────────────────────────────

def _prime_factorization(n: sp.Integer) -> dict:
    value = int(n)
    if abs(value) < 2:
        return _result(n, {}, sp.latex(n), [f"${value}$ no tiene factorización en primos."], True)
    factors = sp.factorint(abs(value))
    steps = [f"Descomponemos ${value}$ en **factores primos** dividiendo sucesivamente por el menor primo posible:"]
    rest = abs(value)
    rows = []
    for p, k in factors.items():
        for _ in range(k):
            rows.append(f"{rest} & {p}")
            rest //= p
    rows.append("1 &")
    steps.append(r"$$\begin{array}{r|l} " + r" \\ ".join(rows) + r" \end{array}$$")
    product = r" \cdot ".join(f"{p}^{{{k}}}" if k > 1 else f"{p}" for p, k in factors.items())
    final = ("-" if value < 0 else "") + product
    steps.append(f"**Resultado:** $${value} = {final}$$")
    verified = sp.prod(p**k for p, k in factors.items()) == abs(value)
    return _result(n, {sp.Integer(p): sp.Integer(k) for p, k in factors.items()}, final, steps, verified)


def _factor_steps(expr, var) -> list[str]:
    steps = []
    gcd_terms = sp.gcd_terms(expr)
    if gcd_terms != expr and not isinstance(gcd_terms, sp.Add):
        steps.append(f"**Factor común:** $${sp.latex(gcd_terms)}$$")
    try:
        poly = sp.Poly(expr, var)
    except sp.PolynomialError:
        return steps
    deg = poly.degree()
    coeffs = poly.all_coeffs()
    if deg == 2:
        a, b, c = coeffs
        disc = b**2 - 4 * a * c
        steps.append(f"Es un polinomio de grado 2: buscamos sus raíces con la fórmula resolvente ($\\Delta = {sp.latex(disc)}$).")
        steps.append(r"Si $r_1, r_2$ son las raíces, $a x^2 + b x + c = a\,(x - r_1)(x - r_2)$.")
    elif deg >= 3:
        terms = [c for c in coeffs if c != 0]
        if len(terms) == 2 and coeffs[-1] != 0:
            kind = "suma" if (coeffs[0] > 0) == (coeffs[-1] > 0) else "diferencia"
            steps.append(f"Es una **{kind} de potencias**: usamos $a^n \\mp b^n$ y el cociente notable correspondiente.")
        else:
            roots = [r for r in sp.roots(poly, filter="Q")]
            if roots:
                steps.append("Buscamos **raíces racionales** (divisores del término independiente sobre divisores del coeficiente principal) "
                             f"y aplicamos **Ruffini**: raíces racionales ${SEP.join(sp.latex(r) for r in roots)}$.")
    return steps


def factor(latex_expr: str) -> dict:
    expr, err = _parse_expression(latex_expr, r"x^3 - 8")
    if err:
        return err
    if expr.is_Integer:
        return _prime_factorization(expr)
    if expr.is_Rational:
        num, den = sp.fraction(expr)
        return _result(expr, expr, sp.latex(expr),
                       [f"$${sp.latex(expr)} = \\frac{{{sp.latex(sp.factorint(num, visual=True))}}}{{{sp.latex(sp.factorint(den, visual=True))}}}$$"],
                       True)

    var = pick_variable(expr)
    steps = [f"Queremos **factorizar**: $${sp.latex(expr)}$$"]
    steps.extend(_factor_steps(sp.expand(expr), var))
    fact = sp.factor(expr)
    if sp.expand(fact) == sp.expand(expr) and fact == sp.expand(expr):
        steps.append("El polinomio es **irreducible** sobre los racionales.")
        try:
            real_roots = [r for r in sp.Poly(expr, var).all_roots() if r.is_real]
            if real_roots and sp.degree(expr, var) == 2:
                lead = sp.LC(expr, var)
                over_r = lead * sp.Mul(*[(var - r) for r in real_roots], evaluate=False)
                steps.append(f"Sobre los reales, con sus raíces irracionales: $${sp.latex(over_r)}$$")
        except Exception:
            pass
    steps.append(f"**Resultado:** $${sp.latex(fact)}$$")
    verified = _equivalent(expr, fact, var)
    if verified:
        steps.append("✓ Verificación: al desarrollar la forma factorizada se obtiene la expresión original.")
    return _result(expr, fact, sp.latex(fact), steps, verified, _graph(expr, var))


# ── Expand ───────────────────────────────────────────────────────────────────

def expand(latex_expr: str) -> dict:
    expr, err = _parse_expression(latex_expr, r"(x + 2)^3")
    if err:
        return err
    var = pick_variable(expr)
    steps = [f"Queremos **desarrollar**: $${sp.latex(expr)}$$"]
    powers = [p for p in expr.atoms(sp.Pow) if p.base.is_Add and p.exp.is_Integer and p.exp > 1]
    if powers:
        steps.append(r"Usamos el **binomio de Newton**: $$(a + b)^n = \sum_{k=0}^{n} \binom{n}{k} a^{n-k} b^k$$")
    if any(isinstance(m, sp.Mul) and sum(1 for f in m.args if f.is_Add) >= 1 for m in sp.preorder_traversal(expr)):
        steps.append("Aplicamos la **propiedad distributiva** y agrupamos términos semejantes.")
    result = sp.expand(expr)
    steps.append(f"**Resultado:** $${sp.latex(result)}$$")
    return _result(expr, result, sp.latex(result), steps, _equivalent(expr, result, var), _graph(expr, var))


# ── Partial fractions ────────────────────────────────────────────────────────

def partial_fractions(latex_expr: str) -> dict:
    expr, err = _parse_expression(latex_expr, r"\frac{3x + 5}{x^2 + 3x + 2}")
    if err:
        return err
    var = pick_variable(expr)
    if not expr.is_rational_function(var):
        return error_result(latex_expr, "Las fracciones parciales se aplican a cocientes de polinomios.")
    num, den = sp.fraction(sp.together(expr))
    steps = [f"Queremos descomponer en **fracciones parciales**: $${sp.latex(expr)}$$",
             f"Factorizamos el denominador: $${sp.latex(den)} = {sp.latex(sp.factor(den))}$$"]
    if sp.degree(num, var) >= sp.degree(den, var):
        q, r = sp.div(num, den, var)
        steps.append(f"Como el grado del numerador no es menor, primero dividimos: cociente ${sp.latex(q)}$, resto ${sp.latex(r)}$.")
    steps.append("Planteamos una fracción por cada factor del denominador (con potencias crecientes si el factor se repite) "
                 "y hallamos los coeficientes igualando numeradores.")
    result = sp.apart(expr, var)
    steps.append(f"**Resultado:** $${sp.latex(result)}$$")
    return _result(expr, result, sp.latex(result), steps, _equivalent(expr, result, var), _graph(expr, var))


# ── Taylor ───────────────────────────────────────────────────────────────────

_CENTER = re.compile(r"(?:\ben\b|alrededor\s+de|centrad[oa]\s+en|\bat\b|around|,)\s*([a-z])\s*=\s*([^,]+?)\s*(?=,|\borden\b|\bgrado\b|\border\b|$)",
                     re.IGNORECASE)
_ORDER = re.compile(r"(?:\borden\b|\bgrado\b|\border\b|\bn\s*=)\s*(\d+)|(?:hasta|up\s+to)\s+(?:el\s+)?(?:orden|grado)?\s*(\d+)",
                    re.IGNORECASE)


def _taylor_params(body: str):
    s = re.sub(r"\\(?:text|mathrm)\s*\{([^}]*)\}", r" \1 ", clean_latex(body))
    order = 5
    m = _ORDER.search(s)
    if m:
        order = int(m.group(1) or m.group(2))
        s = s[:m.start()] + s[m.end():]
    center, var = sp.Integer(0), None
    m = _CENTER.search(s)
    if m:
        var, center = sp.Symbol(m.group(1)), parse_math(m.group(2))
        s = s[:m.start()] + s[m.end():]
    s = re.sub(r"[,;]\s*$", "", s.strip()).strip()
    return s, var, center, min(order, 12)


def taylor(latex_expr: str) -> dict:
    body, var, center, order = _taylor_params(latex_expr)
    expr, err = _parse_expression(body, r"\text{Taylor de } e^{x} \text{ en } x = 0 \text{ orden } 4")
    if err:
        return err
    if center is None:
        return error_result(latex_expr, "No se pudo leer el punto de desarrollo (por ejemplo: en x = 0).")
    var = var or pick_variable(expr)
    v, a = sp.latex(var), sp.latex(center)
    name = "Maclaurin" if center == 0 else "Taylor"
    steps = [f"Buscamos el **polinomio de {name}** de orden ${order}$ de $f({v}) = {sp.latex(expr)}$ alrededor de ${v} = {a}$:",
             f"$$P_{{{order}}}({v}) = \\sum_{{k=0}}^{{{order}}} \\frac{{f^{{(k)}}({a})}}{{k!}}\\,({v} - {a})^k$$"]

    rows, poly = [], sp.Integer(0)
    derivative = expr
    for k in range(order + 1):
        value = sp.simplify(sp.limit(derivative, var, center))
        if not value.is_finite:
            return error_result(latex_expr, f"La función no es derivable en {v} = {a}: no tiene desarrollo de Taylor ahí.")
        rows.append(f"f^{{({k})}}({a}) = {sp.latex(value)}")
        poly += value / sp.factorial(k) * (var - center) ** k
        derivative = sp.diff(derivative, var)
    steps.append("Calculamos las derivadas en el punto: $$" + r" \\ ".join(rows) + "$$" if order <= 6
                 else "Calculamos las derivadas en el punto: $$" + SEP.join(rows) + "$$")
    poly = sp.expand(poly) if center == 0 else poly
    steps.append(f"**Resultado:** $$P_{{{order}}}({v}) = {sp.latex(poly)}$$")

    # The defining property: P and f have the same derivatives at the center up to the order
    verified = all(sp.simplify(sp.diff(poly, var, k).subs(var, center) - sp.limit(sp.diff(expr, var, k), var, center)) == 0
                   for k in range(order + 1))
    graph = None
    if expr.free_symbols == {var}:
        c = float(center) if center.is_real else 0.0
        graph = {"var": var, "curves": [{"expr": expr, "label": "f(x)"}, {"expr": poly, "label": f"P_{order}(x)"}],
                 "x_range": (c - 4, c + 4)}
    return _result(expr, poly, f"P_{{{order}}}({v}) = {sp.latex(poly)}", steps, verified, graph)
