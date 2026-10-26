"""
Series and sequences: finite sums, convergence of infinite series and their value.
"""
import logging

import sympy as sp

from engines.math.common import clean_latex, parse_math, error_result

logger = logging.getLogger(__name__)


def _convergence_test(term, n) -> list[str]:
    """Explain a convergence criterion that applies to the general term."""
    steps = []
    try:
        lim_term = sp.limit(term, n, sp.oo)
        if lim_term != 0:
            steps.append(
                f"**Condición necesaria:** $\\lim_{{n\\to\\infty}} a_n = {sp.latex(lim_term)} \\neq 0$, "
                "por lo tanto la serie **diverge**."
            )
            return steps
        steps.append(r"**Condición necesaria:** $\lim_{n\to\infty} a_n = 0$ (se cumple, pero no alcanza para asegurar convergencia).")
    except Exception:
        pass

    # p-series / comparison with 1/n^p
    try:
        p = sp.limit(-sp.log(sp.Abs(term)) / sp.log(n), n, sp.oo)
        if p.is_number and p.is_finite and not term.has(sp.exp) and not any(
                isinstance(q, sp.Pow) and q.exp.has(n) for q in term.atoms(sp.Pow)):
            verdict = "converge" if p > 1 else "diverge"
            steps.append(
                f"Comparamos con la **serie p** $\\sum \\frac{{1}}{{n^p}}$: el término general se comporta como "
                f"$\\frac{{1}}{{n^{{{sp.latex(p)}}}}}$, con $p = {sp.latex(p)}$ ⇒ {verdict} (converge sii $p > 1$)."
            )
            return steps
    except Exception:
        pass

    # Ratio test (useful with factorials and exponentials)
    try:
        ratio = sp.limit(sp.Abs(sp.simplify(term.subs(n, n + 1) / term)), n, sp.oo)
        if ratio.is_number:
            verdict = ("converge" if ratio < 1 else "diverge" if ratio > 1 else "no concluyente")
            steps.append(
                f"**Criterio del cociente (D'Alembert):** $\\lim_{{n\\to\\infty}} \\left|\\frac{{a_{{n+1}}}}{{a_n}}\\right| = {sp.latex(ratio)}$ ⇒ {verdict}."
            )
    except Exception:
        pass
    return steps


def solve_series(latex_expr: str) -> dict:
    parsed = parse_math(clean_latex(latex_expr))
    if not isinstance(parsed, (sp.Sum, sp.Product)):
        return error_result(latex_expr, r"Ejemplo: `\sum_{n=1}^{\infty} \frac{1}{n^2}`")

    term = parsed.function
    n, a, b = parsed.limits[0]
    is_product = isinstance(parsed, sp.Product)
    sym = r"\prod" if is_product else r"\sum"
    sum_l = f"{sym}_{{{sp.latex(n)}={sp.latex(a)}}}^{{{sp.latex(b)}}} {sp.latex(term)}"
    steps = [f"Tenemos la {'productoria' if is_product else 'serie'}: $${sum_l}$$",
             f"Término general: $a_{{{sp.latex(n)}}} = {sp.latex(term)}$"]

    infinite = b in (sp.oo, -sp.oo)
    if infinite and not is_product:
        steps.extend(_convergence_test(term, n))

    try:
        value = sp.simplify(parsed.doit())
    except Exception as e:
        logger.warning(f"series doit failed: {e}")
        value = parsed

    if infinite and not is_product:
        try:
            converges = parsed.is_convergent()
        except Exception:
            converges = None
        if converges is False or value in (sp.oo, -sp.oo):
            steps.append("**Conclusión:** la serie **diverge**.")
            return {"symbolic": str(parsed), "final_latex": r"\text{Diverge}", "steps": steps, "show_graph": False}

    if isinstance(value, (sp.Sum, sp.Product)):
        try:
            approx = sp.N(parsed, 10)
            steps.append(f"No hay forma cerrada conocida; el valor numérico es $\\approx {sp.latex(approx)}$.")
            final = f"\\approx {sp.latex(approx)}"
        except Exception:
            final = r"\text{Converge (sin forma cerrada)}"
    else:
        if not infinite and not is_product:
            steps.append("Es una **suma finita**; usamos fórmulas cerradas de sumatorias (p. ej. $\\sum k = \\frac{n(n+1)}{2}$).")
        if term.is_number is False and sp.simplify(term.subs(n, n + 1) / term).is_number and not is_product:
            r = sp.simplify(term.subs(n, n + 1) / term)
            steps.append(f"Es una **serie geométrica** de razón $r = {sp.latex(r)}$" +
                         (r", y como $|r| < 1$ usamos $\sum_{n=0}^{\infty} a r^n = \frac{a}{1-r}$." if infinite else "."))
        final = sp.latex(value)
        if value.is_number and not value.is_Rational:
            final += f" \\approx {sp.latex(sp.N(value, 6))}"
        steps.append(f"**Resultado:** $${sum_l} = {final}$$")

    return {"symbolic": str(parsed), "final_latex": final, "steps": steps, "show_graph": False}
