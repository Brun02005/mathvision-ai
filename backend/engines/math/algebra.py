"""
Algebra solver — handles equations, systems, polynomials.
Uses SymPy for exact symbolic computation.
"""
import sympy as sp
from sympy.parsing.latex import parse_latex
import re
import logging

logger = logging.getLogger(__name__)


def _parse(expr_str: str):
    """Try parse_latex first, then sympify as fallback."""
    try:
        return parse_latex(expr_str.strip())
    except Exception:
        pass
    try:
        cleaned = (expr_str
                   .replace(r'\cdot', '*').replace(r'\times', '*')
                   .replace(r'\div', '/').replace(r'\left', '').replace(r'\right', '')
                   .replace(r'\,', '').replace('^', '**'))
        return sp.sympify(cleaned)
    except Exception:
        return None


def solve_equation(latex_expr: str) -> dict:
    """
    Solve an equation or evaluate/simplify an expression.
    Handles: linear, quadratic, polynomial, trigonometric, exponential.
    """
    x = sp.Symbol('x')

    # ── Split on '=' to build Eq ─────────────────────────────────────────────
    if '=' in latex_expr:
        parts = latex_expr.split('=', 1)
        lhs = _parse(parts[0])
        rhs = _parse(parts[1])
        if lhs is None or rhs is None:
            return _fallback(latex_expr)
        eq = sp.Eq(lhs, rhs)
    else:
        # No '=' → treat as expression = 0 or just simplify
        expr = _parse(latex_expr)
        if expr is None:
            return _fallback(latex_expr)
        # If it looks numeric, just evaluate
        if expr.free_symbols == set():
            val = sp.simplify(expr)
            return {
                "symbolic": str(expr),
                "final_latex": sp.latex(val),
                "steps": [
                    f"Evaluamos la expresión: $${sp.latex(expr)}$$",
                    f"**Resultado:** $${sp.latex(val)}$$",
                ],
                "show_graph": False,
            }
        eq = sp.Eq(expr, 0)

    # ── Choose variable to solve for ─────────────────────────────────────────
    free = list(eq.free_symbols)
    var = x if x in free else (free[0] if free else x)

    # ── Solve ────────────────────────────────────────────────────────────────
    try:
        solutions = sp.solve(eq, var)
    except Exception as e:
        logger.warning(f"solve() failed: {e}")
        solutions = []

    if not solutions:
        # Try nsolve for numeric approximation
        try:
            sol_num = sp.nsolve(eq, var, 0)
            solutions = [sol_num]
        except Exception:
            pass

    if not solutions:
        return {
            "symbolic": str(eq),
            "final_latex": r"\text{Sin solución real}",
            "steps": [
                f"Planteamos la ecuación: $${sp.latex(eq)}$$",
                "No se encontraron soluciones reales para esta ecuación.",
            ],
            "show_graph": False,
        }

    # ── Format solutions ─────────────────────────────────────────────────────
    sols_latex = [sp.latex(sp.nsimplify(s, rational=False)) for s in solutions]
    if len(sols_latex) == 1:
        final_latex = f"{sp.latex(var)} = {sols_latex[0]}"
    else:
        sols_str = ",\\quad ".join(sols_latex)
        final_latex = f"{sp.latex(var)} \\in \\left\\{{{sols_str}\\right\\}}"

    # ── Build steps ──────────────────────────────────────────────────────────
    eq_latex = sp.latex(eq)
    steps = _build_equation_steps(eq, eq_latex, var, solutions, sols_latex, latex_expr)

    return {
        "symbolic": str(eq),
        "final_latex": final_latex,
        "steps": steps,
        "show_graph": len(solutions) > 0 and eq.free_symbols != set(),
    }


def _build_equation_steps(eq, eq_latex, var, solutions, sols_latex, original):
    """Generate human-readable steps in Spanish."""
    steps = []

    lhs, rhs = eq.args
    lhs_latex = sp.latex(lhs)
    rhs_latex  = sp.latex(rhs)
    var_latex  = sp.latex(var)

    # Step 1: identify type
    degree = sp.degree(lhs - rhs, var) if (lhs - rhs).is_polynomial(var) else None
    if degree == 1:
        tipo = "ecuación lineal"
    elif degree == 2:
        tipo = "ecuación cuadrática"
    elif degree is not None and degree > 2:
        tipo = f"ecuación polinomial de grado {degree}"
    else:
        tipo = "ecuación"

    steps.append(f"Identificamos una **{tipo}**: $${eq_latex}$$")
    steps.append(f"Despejamos la variable $${var_latex}$$.")

    # If quadratic, mention formula
    if degree == 2:
        coeffs = sp.Poly(lhs - rhs, var).all_coeffs()
        if len(coeffs) == 3:
            a, b, c = [sp.latex(co) for co in coeffs]
            steps.append(
                f"Coeficientes: $a = {a}$, $b = {b}$, $c = {c}$."
            )
            steps.append(
                r"Aplicamos la fórmula cuadrática: $$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$"
            )

    # Solutions
    if len(solutions) == 1:
        steps.append(f"**Solución:** $${var_latex} = {sols_latex[0]}$$")
    else:
        for i, (sol, sol_l) in enumerate(zip(solutions, sols_latex), 1):
            steps.append(f"**Solución {i}:** $${var_latex} = {sol_l}$$")

    # Verification
    if len(solutions) <= 3:
        for sol, sol_l in zip(solutions, sols_latex):
            try:
                check = eq.subs(var, sol)
                if check == True:
                    steps.append(f"✓ Verificación: al sustituir $${var_latex} = {sol_l}$$ la ecuación se cumple.")
            except Exception:
                pass

    return steps


def _fallback(latex_expr: str) -> dict:
    return {
        "symbolic": latex_expr,
        "final_latex": r"\text{No se pudo interpretar la expresión}",
        "steps": [
            "No se pudo interpretar la expresión matemática.",
            "Verificá que esté correctamente escrita.",
            f"Expresión recibida: `{latex_expr}`",
        ],
        "show_graph": False,
    }
