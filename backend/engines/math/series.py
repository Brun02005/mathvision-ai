"""
Series and sequences: finite sums, convergence of infinite series and their value.

A divergent series must never be shown with a number: partial sums of
Σ 1/√n can be evaluated to a huge value that looks like an answer. The value is
only reported when convergence is established (by a criterion or by SymPy).
"""
import logging

import sympy as sp

from engines.math.common import clean_latex, parse_math, error_result, unsolved_result

logger = logging.getLogger(__name__)


def _is_alternating(term, n) -> bool:
    try:
        signs = {sp.sign(sp.N(term.subs(n, k))) for k in range(1000, 1006)}
    except Exception:
        return False
    return signs == {1, -1}


def _convergence_test(term, n, start) -> tuple[list[str], str | None]:
    """Explain a convergence criterion that applies. Returns (steps, "converge" | "diverge" | None)."""
    steps = []
    try:
        lim_term = sp.limit(term, n, sp.oo)
        if lim_term != 0:
            shown = sp.latex(lim_term) if not lim_term.has(sp.AccumBounds) else r"\text{no existe}"
            steps.append(f"**Condición necesaria:** $\\lim_{{n\\to\\infty}} a_n = {shown} \\neq 0$, "
                         "por lo tanto la serie **diverge**.")
            return steps, "diverge"
        steps.append(r"**Condición necesaria:** $\lim_{n\to\infty} a_n = 0$ (se cumple, pero no alcanza para asegurar convergencia).")
    except Exception:
        pass

    alternating = _is_alternating(term, n)
    if alternating:
        # Leibniz: (-1)^n b_n with b_n decreasing to 0 converges (maybe only conditionally)
        b = sp.Abs(term)
        try:
            far = [sp.N(b.subs(n, k)) for k in (10**3, 2 * 10**3, 4 * 10**3)]
            if sp.limit(b, n, sp.oo) == 0 and far[0] > far[1] > far[2]:
                steps.append("Es una **serie alternada** y $|a_n|$ decrece a $0$: por el **criterio de Leibniz**, la serie **converge**.")
                return steps, "converge"
        except Exception:
            pass

    # Limit comparison with 1/n^p: only valid when a_n · n^p tends to a finite non-zero constant.
    # With terms of changing sign it only proves ABSOLUTE convergence, never divergence.
    try:
        p = sp.limit(-sp.log(sp.Abs(term)) / sp.log(n), n, sp.oo)
        if p.is_number and p.is_finite and not (alternating and p <= 1):
            ratio = sp.limit(sp.Abs(term) * n**p, n, sp.oo)
            if ratio.is_positive and ratio.is_finite:
                verdict = "converge" if p > 1 else "diverge"
                steps.append(
                    f"**Comparación por paso al límite** con la serie p $\\sum \\frac{{1}}{{n^p}}$: "
                    f"$\\lim_{{n\\to\\infty}} |a_n|\\, n^{{{sp.latex(p)}}} = {sp.latex(ratio)}$, finito y no nulo, "
                    f"y como $p = {sp.latex(p)}$ la serie **{verdict}** (la serie p converge si y solo si $p > 1$).")
                return steps, verdict
    except Exception:
        pass

    # Ratio test (factorials and exponentials)
    try:
        ratio = sp.limit(sp.Abs(sp.simplify(term.subs(n, n + 1) / term)), n, sp.oo)
        if ratio.is_number and ratio != 1:
            verdict = "converge" if ratio < 1 else "diverge"
            steps.append(f"**Criterio del cociente (D'Alembert):** $\\lim_{{n\\to\\infty}} \\left|\\frac{{a_{{n+1}}}}{{a_n}}\\right| "
                         f"= {sp.latex(ratio)}$ ⇒ la serie **{verdict}**.")
            return steps, verdict
    except Exception:
        pass

    # Integral test, for terms that are eventually positive and decreasing
    try:
        far = [sp.N(term.subs(n, k)) for k in (10**3, 2 * 10**3, 4 * 10**3)]
        if all(v.is_positive for v in far) and far[0] > far[1] > far[2]:
            t = sp.Symbol("t", positive=True)
            area = sp.integrate(term.subs(n, t), (t, max(start, 2), sp.oo))
            if not area.has(sp.Integral):
                verdict = "diverge" if area in (sp.oo, sp.zoo) else "converge"
                steps.append(f"**Criterio de la integral:** el término es positivo y decreciente, y "
                             f"$\\int^{{\\infty}} {sp.latex(term.subs(n, t))}\\,dt = {sp.latex(area)}$ ⇒ la serie **{verdict}**.")
                return steps, verdict
    except Exception:
        pass
    return steps, None


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
    verdict = None
    if infinite and not is_product:
        test_steps, verdict = _convergence_test(term, n, a)
        steps.extend(test_steps)
        if verdict is None:
            try:
                converges = parsed.is_convergent()
                verdict = {True: "converge", False: "diverge"}.get(bool(converges)) if converges in (True, False) else None
            except Exception:
                verdict = None
        if verdict == "diverge":
            steps.append("**Conclusión:** la serie **diverge**.")
            return {"symbolic": str(parsed), "final_latex": r"\text{Diverge}", "steps": steps,
                    "answer": "diverge", "show_graph": False}

    try:
        value = sp.simplify(parsed.doit())
    except Exception as e:
        logger.warning(f"series doit failed: {e}")
        value = parsed

    if infinite and not is_product and (value in (sp.oo, -sp.oo, sp.zoo) or value.has(sp.AccumBounds, sp.nan)):
        steps.append("**Conclusión:** la serie **diverge**.")
        return {"symbolic": str(parsed), "final_latex": r"\text{Diverge}", "steps": steps,
                "answer": "diverge", "show_graph": False}

    answer = value
    if isinstance(value, (sp.Sum, sp.Product)) or value.has(sp.Sum):
        if infinite and verdict != "converge":
            return unsolved_result(parsed, steps, "No pudimos determinar si la serie converge, así que no mostramos un valor.")
        try:
            approx = sp.N(parsed, 10)
        except Exception:
            approx = None
        if approx is None or not approx.is_number:
            return unsolved_result(parsed, steps, "La serie converge, pero no pudimos calcular su suma.")
        steps.append(f"No hay forma cerrada conocida; el valor numérico es $\\approx {sp.latex(approx)}$.")
        final, answer = f"\\approx {sp.latex(approx)}", approx
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

    return {"symbolic": str(parsed), "final_latex": final, "steps": steps, "answer": answer, "show_graph": False}
