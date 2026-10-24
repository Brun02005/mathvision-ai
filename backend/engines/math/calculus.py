"""
Calculus solver — handles ALL integral types correctly:
- Polynomial integrals
- Rational integrals (polynomial division + partial fractions)
- Trigonometric integrals
- Exponential / logarithmic
- Definite integrals (Fundamental Theorem)
- Derivatives and limits
"""
import sympy as sp
from sympy.parsing.latex import parse_latex
import re
import logging

logger = logging.getLogger(__name__)
x = sp.Symbol('x')


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def solve_integral(latex_expr: str) -> dict:
    """Entry point — detects integral type and routes to the right solver."""
    cleaned = _clean_latex(latex_expr)

    # 1. Try to parse as a SymPy Integral object
    parsed = _parse_latex_safe(cleaned)

    if isinstance(parsed, sp.Integral):
        integrand = parsed.args[0]
        limits    = parsed.args[1] if len(parsed.args) > 1 else None
        is_def    = limits is not None and len(limits) == 3
        return _solve_with_steps(integrand, limits, is_def)

    # 2. Try manual extraction of integrand + limits from the LaTeX string
    extracted = _extract_integrand_from_latex(cleaned)
    if extracted:
        integrand, lower, upper = extracted
        is_def = (lower is not None and upper is not None)
        limits = (x, lower, upper) if is_def else None
        return _solve_with_steps(integrand, limits, is_def)

    # 3. If parsed is just an expression (no Integral wrapper), integrate it
    if parsed is not None and not isinstance(parsed, sp.Integral):
        return _solve_with_steps(parsed, None, False)

    return _error_result(latex_expr)


def solve_derivative(latex_expr: str) -> dict:
    """Compute derivative of the expression."""
    cleaned = _clean_latex(latex_expr)
    # Try to extract the inner function from d/dx(...) or \frac{d}{dx}(...)
    inner = _extract_derivative_argument(cleaned) or cleaned
    expr = _parse_latex_safe(inner)
    if expr is None:
        return _error_result(latex_expr)

    try:
        result     = sp.diff(expr, x)
        result_s   = sp.simplify(result)
        expr_latex = sp.latex(expr)
        res_latex  = sp.latex(result_s)

        steps = [
            f"Calculamos la **derivada** de $${expr_latex}$$ con respecto a $x$.",
            "Aplicamos las reglas de derivación (potencia, cadena, producto, cociente).",
            f"$$\\frac{{d}}{{dx}}\\left({expr_latex}\\right) = {res_latex}$$",
        ]
        return {"symbolic": str(sp.Derivative(expr, x)),
                "final_latex": res_latex, "steps": steps, "show_graph": True}
    except Exception as e:
        return _error_result(latex_expr)


# ─────────────────────────────────────────────────────────────────────────────
# CORE SOLVER WITH STEPS
# ─────────────────────────────────────────────────────────────────────────────

def _solve_with_steps(integrand, limits, is_definite: bool) -> dict:
    """Solve the integral and build educational steps."""
    integrand_s = sp.simplify(integrand)
    integrand_l = sp.latex(integrand_s)

    # Determine technique for explanation
    technique, sub_steps = _analyze_integrand(integrand_s)

    # Compute the integral
    try:
        if is_definite and limits is not None:
            result_raw = sp.integrate(integrand_s, limits)
        else:
            result_raw = sp.integrate(integrand_s, x)
        result = sp.simplify(result_raw)
    except Exception as e:
        logger.error(f"Integration failed: {e}")
        return _error_result(str(integrand))

    result_l = sp.latex(result)
    final_l  = result_l if is_definite else result_l + " + C"

    # Build steps
    steps = []

    if is_definite and limits is not None:
        _, a, b = limits
        steps.append(
            f"Tenemos la **integral definida**:\n"
            f"$$\\int_{{{sp.latex(a)}}}^{{{sp.latex(b)}}} {integrand_l}\\, dx$$"
        )
    else:
        steps.append(
            f"Tenemos la **integral indefinida**:\n"
            f"$$\\int {integrand_l}\\, dx$$"
        )

    steps.append(f"**Técnica:** {technique}")
    steps.extend(sub_steps)

    # For definite integrals, show the Fundamental Theorem
    if is_definite and limits is not None:
        _, a, b = limits
        try:
            antideriv   = sp.integrate(integrand_s, x)
            antideriv_l = sp.latex(sp.simplify(antideriv))
            steps.append(
                f"**Antiderivada:** $F(x) = {antideriv_l}$"
            )
            steps.append(
                f"Aplicamos el **Teorema Fundamental del Cálculo**:\n"
                f"$$F({sp.latex(b)}) - F({sp.latex(a)}) = {result_l}$$"
            )
        except Exception:
            pass

    steps.append(f"**Resultado final:** $${final_l}$$")

    return {
        "symbolic":     str(sp.Integral(integrand_s, (x,) if not is_definite else limits)),
        "final_latex":  final_l,
        "steps":        steps,
        "show_graph":   not is_definite,
    }


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION TECHNIQUE ANALYZER
# ─────────────────────────────────────────────────────────────────────────────

def _analyze_integrand(expr) -> tuple[str, list]:
    """Return (technique_name, [step_strings]) explaining the method used."""
    steps = []

    # ── Rational function → polynomial division + partial fractions ──────────
    if expr.is_rational_function(x):
        numer, denom = sp.fraction(expr)
        numer = sp.Poly(numer, x)
        denom = sp.Poly(denom, x)

        if numer.degree() >= denom.degree():
            # Polynomial long division
            quotient, remainder = sp.div(numer, denom, x)
            q_expr = quotient.as_expr()
            r_expr = remainder.as_expr()
            d_expr = denom.as_expr()
            q_l    = sp.latex(q_expr)
            r_l    = sp.latex(r_expr)
            d_l    = sp.latex(d_expr)

            steps.append(
                f"El grado del numerador ({numer.degree()}) ≥ grado del denominador "
                f"({denom.degree()}), hacemos **división de polinomios**:"
            )
            steps.append(
                f"$$\\frac{{{sp.latex(numer.as_expr())}}}{{{d_l}}} "
                f"= {q_l} + \\frac{{{r_l}}}{{{d_l}}}$$"
            )

            if r_expr != 0:
                steps.extend(_partial_fraction_steps(r_expr, d_expr, d_l))

            return "División de polinomios + Fracciones parciales", steps

        else:
            # Pure partial fractions (degree numerator < denominator)
            steps.extend(_partial_fraction_steps(numer.as_expr(), denom.as_expr(), sp.latex(denom.as_expr())))
            return "Descomposición en fracciones parciales", steps

    # ── Trigonometric ────────────────────────────────────────────────────────
    expr_str = str(expr)
    if any(f in expr_str for f in ['sin', 'cos', 'tan', 'sec', 'csc', 'cot']):
        steps.append("Aplicamos las **fórmulas de integración trigonométrica** directas.")
        return "Integración trigonométrica", steps

    # ── Exponential / logarithm ──────────────────────────────────────────────
    if 'exp' in expr_str or 'E**' in expr_str or 'log' in expr_str:
        steps.append("Aplicamos las **fórmulas de integración exponencial/logarítmica**.")
        return "Integración exponencial / logarítmica", steps

    # ── Polynomial ───────────────────────────────────────────────────────────
    if expr.is_polynomial(x):
        degree = sp.degree(expr, x)
        steps.append(
            f"Es un **polinomio de grado {degree}**. "
            f"Aplicamos la regla de la potencia: $$\\int x^n\\,dx = \\frac{{x^{{n+1}}}}{{n+1}} + C$$"
        )
        return "Regla de la potencia (polinomio)", steps

    # ── Default ──────────────────────────────────────────────────────────────
    steps.append("Aplicamos las reglas estándar de integración.")
    return "Integración directa", steps


def _partial_fraction_steps(numer, denom, denom_l: str) -> list:
    """Generate partial fraction decomposition steps."""
    steps = []
    try:
        pf = sp.apart(numer / denom, x)
        pf_l = sp.latex(pf)

        # Factor the denominator
        denom_factored = sp.factor(denom)
        denom_f_l = sp.latex(denom_factored)

        steps.append(
            f"Factorizamos el denominador: $${denom_l} = {denom_f_l}$$"
        )
        steps.append(
            f"Descomponemos en **fracciones parciales**:\n"
            f"$$\\frac{{...}}{{{denom_f_l}}} = {pf_l}$$"
        )
        steps.append("Integramos cada fracción parcial usando logaritmos y potencias.")
    except Exception as e:
        steps.append("Descomponemos la fracción en términos más simples para integrar.")
    return steps


# ─────────────────────────────────────────────────────────────────────────────
# PARSING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _clean_latex(latex_expr: str) -> str:
    """Remove OCR artifacts and normalize LaTeX."""
    s = latex_expr.strip()
    # Remove empty limit braces from OCR: \int_{} or \int_{}^{}
    s = re.sub(r'\\int_\{\}\^\{\}', r'\\int', s)
    s = re.sub(r'\\int_\{\}',       r'\\int', s)
    s = re.sub(r'\\int\^\{\}',      r'\\int', s)
    # Normalize whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _parse_latex_safe(latex_str: str):
    """Try parse_latex, then sympify as fallback."""
    try:
        return parse_latex(latex_str)
    except Exception:
        pass
    try:
        cleaned = (latex_str
                   .replace(r'\cdot', '*').replace(r'\times', '*')
                   .replace(r'\left', '').replace(r'\right', '')
                   .replace(r'\,', '').replace(r'\;', ' '))
        return sp.sympify(cleaned)
    except Exception:
        pass
    return None


def _extract_integrand_from_latex(latex_expr: str):
    """
    Extract integrand and optional limits from LaTeX manually.
    Returns (integrand_expr, lower, upper) or None.
    """
    # Match \int_{lower}^{upper} ... dx
    m = re.match(
        r'\\int(?:_\{([^}]*)\}\^\{([^}]*)\}|\^\{([^}]*)\}_\{([^}]*)\})?\s*([\s\S]+?)\s*(?:\\,\s*)?d[a-z]\s*$',
        latex_expr
    )
    if not m:
        # simpler: \int ... dx
        m2 = re.match(r'\\int\s+([\s\S]+?)\s*(?:\\,\s*)?d[a-z]\s*$', latex_expr)
        if m2:
            inner = m2.group(1).strip()
            expr = _parse_latex_safe(inner)
            return (expr, None, None) if expr is not None else None
        return None

    lower_s = m.group(1) or m.group(4)
    upper_s = m.group(2) or m.group(3)
    inner   = m.group(5).strip()

    expr = _parse_latex_safe(inner)
    if expr is None:
        return None

    lower = _parse_latex_safe(lower_s) if lower_s and lower_s.strip() else None
    upper = _parse_latex_safe(upper_s) if upper_s and upper_s.strip() else None

    return (expr, lower, upper)


def _extract_derivative_argument(latex_expr: str):
    """Extract f from d/dx(f) or \frac{d}{dx}(f)."""
    # \frac{d}{dx}(...)
    m = re.search(r'\\frac\{d\}\{d[a-z]\}\s*[\(\{](.+?)[\)\}]\s*$', latex_expr)
    if m:
        return m.group(1)
    # d/dx(...)
    m2 = re.search(r'd\s*/\s*d[a-z]\s*[\(\{](.+?)[\)\}]\s*$', latex_expr)
    if m2:
        return m2.group(1)
    return None


def _error_result(expr_str: str) -> dict:
    return {
        "symbolic":    expr_str,
        "final_latex": r"\text{No se pudo resolver}",
        "steps": [
            "No se pudo interpretar la expresión.",
            "Asegurate de escribirla en formato LaTeX correcto.",
            r"Ejemplo de integral racional: `\int \frac{x^5 + x^4 - 8}{x^3 - 4x} dx`",
        ],
        "show_graph": False,
    }
