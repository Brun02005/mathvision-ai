"""
Calculus solver:
- Integrals: polynomial, rational (polynomial division + partial fractions),
  substitution, integration by parts, trigonometric, exponential / logarithmic,
  definite integrals (Fundamental Theorem) and improper integrals.
- Derivatives of any order, explaining which rules apply.
- Limits, including indeterminate forms and L'Hôpital.
"""
import re
import logging

import sympy as sp

from engines.math.common import (
    clean_latex, parse_math, pick_variable, error_result, same_function, split_top_level,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRALS
# ─────────────────────────────────────────────────────────────────────────────

def solve_integral(latex_expr: str) -> dict:
    """Entry point — detects integral type and routes to the right solver."""
    cleaned = clean_latex(latex_expr)
    parsed = parse_math(cleaned)

    if isinstance(parsed, sp.Integral):
        if len(parsed.limits) > 1 or isinstance(parsed.function, sp.Integral):
            return _solve_multiple(parsed)
        integrand = parsed.function
        lim = parsed.limits[0]
        var = lim[0]
        limits = lim if len(lim) == 3 else None
        return _solve_with_steps(integrand, var, limits)

    extracted = _extract_integrand_from_latex(cleaned)
    if extracted:
        integrand, var, lower, upper = extracted
        limits = (var, lower, upper) if lower is not None and upper is not None else None
        return _solve_with_steps(integrand, var, limits)

    if isinstance(parsed, sp.Basic) and not isinstance(parsed, sp.Integral) and parsed.free_symbols:
        return _solve_with_steps(parsed, pick_variable(parsed), None)

    return error_result(latex_expr, r"Ejemplo de integral: `\int \frac{x^5 + x^4 - 8}{x^3 - 4x} dx`")


def _solve_with_steps(integrand, var, limits) -> dict:
    """Solve the integral and build educational steps."""
    is_def = limits is not None
    original_var = var
    if integrand.has(sp.Abs, sp.sign):
        # |x| only integrates cleanly over the reals
        var = sp.Symbol(var.name, real=True)
        integrand = integrand.xreplace({original_var: var})
        if is_def:
            limits = (var, limits[1], limits[2])
    integrand_s = sp.simplify(integrand)
    integrand_l = sp.latex(integrand_s)
    v = sp.latex(var)

    technique, sub_steps = _analyze_integrand(integrand_s, var)

    try:
        antideriv = sp.integrate(integrand_s, var)
        if isinstance(antideriv, sp.Integral) or antideriv.has(sp.Integral):
            antideriv = None
    except Exception as e:
        logger.warning(f"Indefinite integration failed: {e}")
        antideriv = None

    steps = []
    inner_singularities = []
    if is_def:
        _, a, b = limits
        a_l, b_l = sp.latex(a), sp.latex(b)
        steps.append(f"Tenemos la **integral definida**: $$\\int_{{{a_l}}}^{{{b_l}}} {integrand_l}\\, d{v}$$")
        if a.has(sp.oo, -sp.oo) or b.has(sp.oo, -sp.oo):
            steps.append("Es una **integral impropia** (un límite es infinito): la calculamos como límite de integrales definidas.")
        inner_singularities = _singularities_in(integrand_s, var, a, b)
        if inner_singularities:
            pts = ",\\; ".join(f"{v} = {sp.latex(p)}" for p in inner_singularities)
            steps.append(f"El integrando **no está acotado** en ${pts}$, dentro del intervalo: es una **integral impropia** "
                         "y no se puede aplicar Barrow directamente.")
    else:
        steps.append(f"Tenemos la **integral indefinida**: $$\\int {integrand_l}\\, d{v}$$")

    steps.append(f"**Técnica:** {technique}")
    steps.extend(sub_steps)

    antideriv_ok = None
    if antideriv is not None:
        antideriv = sp.simplify(antideriv)
        steps.append(f"**Primitiva:** $$F({v}) = {sp.latex(_with_abs_logs(antideriv, integrand_s, var))}$$")
        antideriv_ok = _is_antiderivative(antideriv, integrand_s, var)
        if antideriv_ok:
            steps.append(f"✓ Verificación: derivando $F$ se recupera el integrando, $F'({v}) = {integrand_l}$.")

    verified = antideriv_ok
    if is_def:
        try:
            result = sp.simplify(sp.integrate(integrand_s, limits))
        except Exception as e:
            logger.error(f"Definite integration failed: {e}")
            return error_result(str(integrand))
        if isinstance(result, sp.Integral):
            result = sp.N(result, 8)
            steps.append("No existe una primitiva elemental; calculamos el valor **numéricamente**.")
        _, a, b = limits
        diverges = (result in (sp.oo, -sp.oo, sp.zoo, sp.nan) or result.has(sp.oo, sp.zoo, sp.nan, sp.AccumBounds))
        if antideriv is not None and not diverges and not inner_singularities and not (a.has(sp.oo, -sp.oo) or b.has(sp.oo, -sp.oo)):
            Fb = sp.simplify(antideriv.subs(var, b))
            Fa = sp.simplify(antideriv.subs(var, a))
            steps.append(
                f"Aplicamos la **Regla de Barrow** (Teorema Fundamental del Cálculo): "
                f"$$F({sp.latex(b)}) - F({sp.latex(a)}) = {sp.latex(Fb)} - \\left({sp.latex(Fa)}\\right) = {sp.latex(result)}$$"
            )
        if diverges:
            steps.append("La integral **diverge** (no converge a un número finito).")
            steps.append("**Resultado final:** la integral diverge.")
            return {"symbolic": str(sp.Integral(integrand_s, limits)), "final_latex": r"\text{Diverge}",
                    "steps": steps, "answer": "diverge", "show_graph": False}
        else:
            answer = result
            verified = _numeric_integral_check(sp.Integral(integrand_s, limits), result)
            if verified:
                steps.append("✓ Verificación numérica: la integración numérica da el mismo valor.")
        final_l = sp.latex(result)
        if result.is_number and not result.is_Rational and result.is_finite:
            final_l += f" \\approx {sp.latex(sp.N(result, 6))}"
    else:
        if antideriv is None:
            return {
                "symbolic": str(sp.Integral(integrand_s, var)),
                "final_latex": r"\text{Sin primitiva elemental}",
                "steps": steps + ["Esta función **no tiene primitiva expresable con funciones elementales**."],
                "answer": "no_elemental",
                "show_graph": False,
            }
        if antideriv_ok is False:
            return {
                "symbolic": str(sp.Integral(integrand_s, var)),
                "final_latex": r"\text{No se pudo verificar}",
                "steps": steps + ["⚠ La primitiva obtenida no superó la verificación, así que no la mostramos como resultado."],
                "show_graph": False,
                "ok": False,
            }
        answer = antideriv
        final_l = sp.latex(_with_abs_logs(antideriv, integrand_s, var)) + " + C"

    steps.append(f"**Resultado final:** $${final_l}$$")

    graph = None
    if integrand_s.free_symbols == {var}:
        curves = [{"expr": integrand_s, "label": "f(x)"}]
        if antideriv is not None and not is_def:
            curves.append({"expr": antideriv, "label": "F(x) (C = 0)"})
        graph = {"var": var, "curves": curves}
        if is_def:
            a_f, b_f = _as_float(limits[1]), _as_float(limits[2])
            if a_f is not None and b_f is not None:
                span = abs(b_f - a_f) or 1
                graph["x_range"] = (min(a_f, b_f) - span * 0.5, max(a_f, b_f) + span * 0.5)
                graph["fill"] = {"a": a_f, "b": b_f}

    return {
        "symbolic": str(sp.Integral(integrand_s, limits or var)),
        "final_latex": final_l,
        "steps": steps,
        "answer": answer.xreplace({var: original_var}) if isinstance(answer, sp.Basic) else answer,
        "verified": verified,
        "show_graph": graph is not None,
        "graph": graph,
    }


def _singularities_in(f, var, a, b) -> list:
    """Points of [a, b] where the integrand blows up (improper integral of the second kind)."""
    try:
        lo, hi = (a, b) if (a < b) == sp.true else (b, a)
        points = sp.singularities(f, var, sp.Interval(lo, hi))
    except Exception:
        return []
    if not isinstance(points, sp.FiniteSet):
        return []
    blowing = []
    for p in points:
        try:
            if any(sp.limit(f, var, p, dir=d).is_finite is False for d in ("+", "-")):
                blowing.append(p)
        except Exception:
            continue
    return blowing


def _with_abs_logs(F, f, var):
    """
    ∫ 1/x dx is ln|x| + C over the reals; SymPy writes log(x). For display only (the
    verified answer keeps SymPy's form): add |·| to logs whose argument can be negative,
    unless the integrand itself has logs (then the domain already forces a positive argument).
    """
    if f.has(sp.log):
        return F
    real_var = sp.Symbol(var.name, real=True)

    def fix(e):
        arg = e.args[0]
        return e if arg.xreplace({var: real_var}).is_positive or isinstance(arg, sp.Abs) else sp.log(sp.Abs(arg))
    return F.replace(lambda e: isinstance(e, sp.log), fix)


def _is_antiderivative(F, f, var) -> bool | None:
    try:
        if sp.simplify(sp.diff(F, var) - f) == 0:
            return True
    except Exception:
        pass
    return same_function(sp.diff(F, var), f, var)


def _numeric_integral_check(integral, value) -> bool | None:
    """Compare the exact value with numerical quadrature (mpmath)."""
    try:
        exact = complex(sp.N(value, 20))
        numeric = complex(integral.evalf(20))
    except (TypeError, ValueError):
        return None
    return abs(exact - numeric) <= 1e-8 * (1 + abs(exact))


def _solve_multiple(parsed) -> dict:
    """Double / triple integrals, solved from the inside out (Fubini)."""
    integral = parsed
    while isinstance(integral.function, sp.Integral):
        inner = integral.function
        integral = sp.Integral(inner.function, *inner.limits, *integral.limits)
    kind = {2: "doble", 3: "triple"}.get(len(integral.limits), "múltiple")
    steps = [f"Tenemos una **integral {kind}**: $${sp.latex(integral)}$$",
             "La resolvemos **de adentro hacia afuera** (teorema de Fubini): en cada integral, "
             "las demás variables se tratan como constantes."]
    current = integral.function
    for lim in integral.limits:
        step_integral = sp.Integral(current, lim)
        current = sp.simplify(step_integral.doit())
        if current.has(sp.Integral):
            return error_result(str(parsed), "Una de las integrales interiores no tiene primitiva elemental.")
        steps.append(f"Integramos respecto de ${sp.latex(lim[0])}$: $${sp.latex(step_integral)} = {sp.latex(current)}$$")
    result = current
    verified = _numeric_integral_check(integral, result) if result.is_number else None
    if verified:
        steps.append("✓ Verificación numérica: la integración numérica da el mismo valor.")
    final = sp.latex(result)
    if result.is_number and not result.is_Rational and result.is_finite:
        final += f" \\approx {sp.latex(sp.N(result, 6))}"
    steps.append(f"**Resultado:** $${final}$$")
    return {"symbolic": str(integral), "final_latex": final, "steps": steps,
            "answer": result, "verified": verified, "show_graph": False}


def _as_float(v):
    try:
        f = float(v)
        return f if abs(f) < 1e6 else None
    except (TypeError, ValueError):
        return None


def _analyze_integrand(expr, var) -> tuple[str, list]:
    """Return (technique_name, [step_strings]) explaining the method used."""
    steps = []
    v = sp.latex(var)

    # ── Rational function → polynomial division + partial fractions ──────────
    if expr.is_rational_function(var) and not expr.is_polynomial(var):
        numer, denom = sp.fraction(sp.together(expr))
        numer, denom = sp.Poly(numer, var), sp.Poly(denom, var)

        if numer.degree() >= denom.degree():
            quotient, remainder = sp.div(numer, denom)
            q_l, r_l, d_l = (sp.latex(p.as_expr()) for p in (quotient, remainder, denom))
            steps.append(
                f"El grado del numerador ({numer.degree()}) ≥ grado del denominador "
                f"({denom.degree()}), hacemos **división de polinomios**:"
            )
            steps.append(f"$$\\frac{{{sp.latex(numer.as_expr())}}}{{{d_l}}} = {q_l} + \\frac{{{r_l}}}{{{d_l}}}$$")
            if not remainder.is_zero:
                steps.extend(_partial_fraction_steps(remainder.as_expr(), denom.as_expr(), var))
            return "División de polinomios + Fracciones parciales", steps

        steps.extend(_partial_fraction_steps(numer.as_expr(), denom.as_expr(), var))
        return "Descomposición en fracciones parciales", steps

    # ── Polynomial ───────────────────────────────────────────────────────────
    if expr.is_polynomial(var):
        steps.append(
            f"Es un **polinomio de grado {sp.degree(expr, var)}**. Integramos término a término con la "
            f"regla de la potencia: $$\\int {v}^n\\,d{v} = \\frac{{{v}^{{n+1}}}}{{n+1}} + C$$"
        )
        return "Regla de la potencia (polinomio)", steps

    # ── Substitution: f(g(x))·g'(x) ──────────────────────────────────────────
    sub = _find_substitution(expr, var)
    if sub is not None:
        g, new_integrand = sub
        steps.append(f"Proponemos la **sustitución** $u = {sp.latex(g)}$, entonces $du = {sp.latex(sp.diff(g, var))}\\, d{v}$.")
        steps.append(f"La integral queda: $$\\int {sp.latex(new_integrand)}\\, du$$")
        return "Sustitución (cambio de variable)", steps

    # ── Integration by parts: polynomial × (exp | trig | log) ────────────────
    parts = _by_parts_choice(expr, var)
    if parts is not None:
        u_, dv_ = parts
        du_, v_ = sp.diff(u_, var), sp.integrate(dv_, var)
        steps.append(r"Aplicamos **integración por partes**: $$\int u\,dv = u\,v - \int v\,du$$")
        steps.append("Elegimos $u$ según la regla **LIATE** (Logarítmica, Inversa trig., Algebraica, Trigonométrica, Exponencial):")
        steps.append(f"$$u = {sp.latex(u_)},\\quad dv = {sp.latex(dv_)}\\,d{v}$$")
        steps.append(f"$$du = {sp.latex(du_)}\\,d{v},\\quad v = {sp.latex(v_)}$$")
        return "Integración por partes", steps

    if expr.has(sp.sin, sp.cos, sp.tan, sp.sec, sp.csc, sp.cot):
        if any(isinstance(p, sp.Pow) and p.base.func in (sp.sin, sp.cos) for p in expr.atoms(sp.Pow)):
            steps.append(r"Usamos identidades trigonométricas para reducir potencias, p. ej. $\sin^2 x = \frac{1 - \cos 2x}{2}$.")
        else:
            steps.append("Aplicamos las **fórmulas de integración trigonométrica** directas.")
        return "Integración trigonométrica", steps

    if expr.has(sp.exp, sp.log) or any(b == sp.E for b, _ in (p.as_base_exp() for p in expr.atoms(sp.Pow))):
        steps.append("Aplicamos las **fórmulas de integración exponencial/logarítmica**.")
        return "Integración exponencial / logarítmica", steps

    steps.append("Aplicamos las reglas estándar de integración.")
    return "Integración directa", steps


def _find_substitution(expr, var):
    """Look for an inner function g(x) such that expr = f(g)·g'. Returns (g, f(u)) or None."""
    u = sp.Symbol('u')
    candidates = set()
    for node in sp.preorder_traversal(expr):
        if isinstance(node, (sp.sin, sp.cos, sp.tan, sp.exp, sp.log)) and node.args[0] != var:
            candidates.add(node.args[0])
        elif isinstance(node, sp.Pow) and node.base != var and node.base.has(var) and not node.base.is_Atom:
            candidates.add(node.base)
    for g in sorted(candidates, key=sp.count_ops, reverse=True):
        dg = sp.diff(g, var)
        if dg == 0:
            continue
        try:
            new = sp.simplify((expr / dg).subs(g, u))
            if not new.has(var):
                return g, new
        except Exception:
            continue
    return None


def _by_parts_choice(expr, var):
    """LIATE choice of u for products like x·e^x, x·sin(x), ln(x)·x^n."""
    if not isinstance(expr, sp.Mul):
        if isinstance(expr, sp.log) or isinstance(expr, (sp.atan, sp.asin, sp.acos)):
            return expr, sp.Integer(1)
        return None
    factors = expr.args
    order = [
        lambda f: f.has(sp.log),
        lambda f: f.has(sp.atan, sp.asin, sp.acos),
        lambda f: f.is_polynomial(var) and f.has(var),
        lambda f: f.has(sp.sin, sp.cos),
        lambda f: f.has(sp.exp) or (isinstance(f, sp.Pow) and f.base == sp.E),
    ]
    for rule in order:
        us = [f for f in factors if f.has(var) and rule(f)]
        if us:
            u_ = us[0]
            dv_ = sp.simplify(expr / u_)
            if dv_.has(var) and not isinstance(sp.integrate(dv_, var), sp.Integral):
                return u_, dv_
            return None
    return None


def _partial_fraction_steps(numer, denom, var) -> list:
    steps = []
    try:
        pf = sp.apart(numer / denom, var)
        denom_f = sp.factor(denom)
        steps.append(f"Factorizamos el denominador: $${sp.latex(denom)} = {sp.latex(denom_f)}$$")
        steps.append(f"Descomponemos en **fracciones parciales**: $$\\frac{{{sp.latex(numer)}}}{{{sp.latex(denom_f)}}} = {sp.latex(pf)}$$")
        steps.append(r"Integramos cada fracción: $\int \frac{A}{x-a}\,dx = A\ln|x-a|$ y potencias/arctangentes para los factores restantes.")
    except Exception:
        steps.append("Descomponemos la fracción en términos más simples para integrar.")
    return steps


def _extract_integrand_from_latex(latex_expr: str):
    """
    Manual fallback: \\int_{a}^{b} f(x) dx  /  \\int f dx.
    Returns (integrand, var, lower, upper) or None.
    """
    m = re.match(
        r'\\int(?:_\{([^}]*)\}\^\{([^}]*)\}|\^\{([^}]*)\}_\{([^}]*)\}|_(\S)\^(\S))?\s*([\s\S]+?)\s*d([a-z])\s*$',
        latex_expr,
    )
    if not m:
        return None
    lower_s = m.group(1) or m.group(4) or m.group(5)
    upper_s = m.group(2) or m.group(3) or m.group(6)
    expr = parse_math(m.group(7).strip())
    if expr is None:
        return None
    var = sp.Symbol(m.group(8))
    lower = parse_math(lower_s) if lower_s and lower_s.strip() else None
    upper = parse_math(upper_s) if upper_s and upper_s.strip() else None
    return expr, var, lower, upper


# ─────────────────────────────────────────────────────────────────────────────
# DERIVATIVES
# ─────────────────────────────────────────────────────────────────────────────

_HIGHER_ORDER = re.compile(r'\\frac\{d\^\{?(\d+)\}?\}\{d([a-z])\^\{?\d+\}?\}\s*(.+)$')
_FIRST_ORDER = re.compile(r'(?:\\frac\{d\}\{d([a-z])\}|d\s*/\s*d([a-z]))\s*(.+)$')


def _strip_outer_parens(s: str) -> str:
    s = s.strip()
    while (s.startswith('(') and s.endswith(')')) or (s.startswith('{') and s.endswith('}')):
        s = s[1:-1].strip()
    return s


def _parse_derivative(cleaned: str):
    """Return (expr, var, order) or None."""
    m = _HIGHER_ORDER.search(cleaned)
    if m:
        expr = parse_math(_strip_outer_parens(m.group(3)))
        return (expr, sp.Symbol(m.group(2)), int(m.group(1))) if expr is not None else None

    parsed = parse_math(cleaned)
    if isinstance(parsed, sp.Derivative):
        var, order = parsed.variable_count[0]
        return parsed.expr, var, int(order)

    m = _FIRST_ORDER.search(cleaned)
    if m:
        expr = parse_math(_strip_outer_parens(m.group(3)))
        return (expr, sp.Symbol(m.group(1) or m.group(2)), 1) if expr is not None else None

    # f'(x) = ... or plain expression → derivative wrt its variable
    m = re.match(r"^\s*[fgh]\s*('+)\s*\(\s*([a-z])\s*\)\s*(?:=\s*(.+))?$", cleaned)
    if m and m.group(3):
        expr = parse_math(m.group(3))
        return (expr, sp.Symbol(m.group(2)), len(m.group(1))) if expr is not None else None

    if isinstance(parsed, sp.Basic) and parsed.free_symbols:
        return parsed, pick_variable(parsed), 1
    return None


def _derivative_rules(expr, var) -> list[str]:
    """Name the differentiation rules that apply, by looking at the expression tree."""
    rules = []
    num, den = sp.fraction(sp.together(expr))
    if den.has(var) and num.has(var):
        rules.append(r"**regla del cociente** $\left(\frac{u}{v}\right)' = \frac{u'v - uv'}{v^2}$")
    elif isinstance(expr, sp.Mul) and sum(1 for f in expr.args if f.has(var)) >= 2:
        rules.append(r"**regla del producto** $(u\,v)' = u'v + u\,v'$")

    composed = any(
        (isinstance(n, sp.Function) and n.args and n.args[0] != var and n.args[0].has(var)) or
        (isinstance(n, sp.Pow) and n.base.has(var) and not n.base.is_Symbol)
        for n in sp.preorder_traversal(expr)
    )
    if composed:
        rules.append(r"**regla de la cadena** $(f(g(x)))' = f'(g(x))\cdot g'(x)$")
    if any(isinstance(p, sp.Pow) and p.base == var for p in expr.atoms(sp.Pow)) or expr.is_polynomial(var):
        rules.append(r"**regla de la potencia** $(x^n)' = n\,x^{n-1}$")
    if expr.has(sp.sin, sp.cos, sp.tan):
        rules.append(r"derivadas trigonométricas $(\sin x)' = \cos x$, $(\cos x)' = -\sin x$")
    if expr.has(sp.exp, sp.log):
        rules.append(r"$(e^x)' = e^x$ y $(\ln x)' = \frac{1}{x}$")
    return rules


_DYDX = re.compile(r"^\s*(?:\\frac\{d\s*([a-z])\}\{d\s*([a-z])\}|d\s*([a-z])\s*/\s*d\s*([a-z])|([a-z])\s*')\s*$")


def implicit_request(latex_expr: str):
    """`x^2 + y^2 = 25, \\frac{dy}{dx}` → (equation, y, x). None if it is not an implicit derivative request."""
    parts = split_top_level(clean_latex(latex_expr), seps=(",", ";"))
    if len(parts) != 2:
        return None
    for asked, other in (parts, parts[::-1]):
        m = _DYDX.match(asked)
        if m and "=" in other and "'" not in other and r"\frac{d" not in other:
            dep = m.group(1) or m.group(3) or m.group(5)
            indep = m.group(2) or m.group(4) or "x"
            return other, sp.Symbol(dep), sp.Symbol(indep)
    return None


def solve_implicit_derivative(latex_expr: str) -> dict:
    eq_s, y, x = implicit_request(latex_expr)
    lhs_s, rhs_s = eq_s.split("=", 1)
    lhs, rhs = parse_math(lhs_s), parse_math(rhs_s)
    if lhs is None or rhs is None:
        return error_result(latex_expr, r"Ejemplo: `x^2 + y^2 = 25, \frac{dy}{dx}`")
    F = lhs - rhs
    yl, xl = sp.latex(y), sp.latex(x)
    try:
        result = sp.simplify(sp.idiff(F, y, x))
    except Exception as e:
        logger.warning(f"idiff failed: {e}")
        return error_result(latex_expr)
    Fx, Fy = sp.diff(F, x), sp.diff(F, y)
    steps = [
        f"La ecuación $${sp.latex(sp.Eq(lhs, rhs))}$$ define ${yl}$ **implícitamente** como función de ${xl}$.",
        f"Derivamos ambos miembros respecto de ${xl}$, tratando ${yl} = {yl}({xl})$: cada vez que derivamos una expresión en ${yl}$ "
        f"aparece el factor $\\frac{{d{yl}}}{{d{xl}}}$ (**regla de la cadena**).",
        f"Agrupamos los términos con $\\frac{{d{yl}}}{{d{xl}}}$ y despejamos. Es equivalente a usar "
        f"$$\\frac{{d{yl}}}{{d{xl}}} = -\\frac{{F_{{{xl}}}}}{{F_{{{yl}}}}} = -\\frac{{{sp.latex(Fx)}}}{{{sp.latex(Fy)}}}$$",
        f"**Resultado:** $$\\frac{{d{yl}}}{{d{xl}}} = {sp.latex(result)}$$",
    ]
    return {"symbolic": str(F), "final_latex": f"\\frac{{d{yl}}}{{d{xl}}} = {sp.latex(result)}", "steps": steps,
            "answer": result, "show_graph": False}


_PARTIAL = re.compile(r"\\frac\{\\partial(?:\^\{?(\d+)\}?)?\s*\}\{((?:[^{}]|\{[^{}]*\})*)\}\s*(.+)$")
_DEFINITION = re.compile(r"^\s*[fghy]\s*(?:\(\s*[a-z]\s*\))?\s*=\s*(.+)$")


def solve_partial_derivative(expr, variables: list[tuple]) -> dict:
    """∂^n f / ∂x ∂y ...: differentiate once per variable in the denominator."""
    result = sp.simplify(sp.diff(expr, *variables))
    denom = " ".join(f"\\partial {sp.latex(v)}" + (f"^{{{k}}}" if k > 1 else "") for v, k in variables)
    total = sum(k for _, k in variables)
    op = f"\\frac{{\\partial{'^{' + str(total) + '}' if total > 1 else ''}}}{{{denom}}}"
    others = sorted({s for s in expr.free_symbols} - {v for v, _ in variables}, key=lambda s: s.name)
    steps = [f"Calculamos la **derivada parcial** $${op}\\left({sp.latex(expr)}\\right)$$"]
    if others:
        steps.append("Las demás variables (" + ", ".join(f"${sp.latex(s)}$" for s in others) + ") se tratan como **constantes**.")
    current = expr
    for v, k in variables:
        for _ in range(k):
            current = sp.simplify(sp.diff(current, v))
            steps.append(f"Derivamos respecto de ${sp.latex(v)}$: $${sp.latex(current)}$$")
    steps.append(f"**Resultado:** $${op}\\left({sp.latex(expr)}\\right) = {sp.latex(result)}$$")
    return {"symbolic": str(sp.Derivative(expr, *variables)), "final_latex": sp.latex(result),
            "steps": steps, "answer": result, "show_graph": False}


def solve_derivative(latex_expr: str) -> dict:
    cleaned = clean_latex(latex_expr)
    if implicit_request(cleaned):
        return solve_implicit_derivative(cleaned)
    m = _PARTIAL.search(cleaned)
    if m:
        variables = [(sp.Symbol(v), int(k or 1)) for v, k in re.findall(r"\\partial\s*([a-z])(?:\^\{?(\d+)\}?)?", m.group(2))]
        expr = parse_math(_strip_outer_parens(m.group(3)))
        if not variables or expr is None:
            return error_result(latex_expr, r"Ejemplo: `\frac{\partial^2}{\partial x \partial y}(x^2 y^3)`")
        return solve_partial_derivative(expr, variables)
    # "derivar f(x) = x^3": differentiate the right-hand side of the definition
    m = _DEFINITION.match(cleaned)
    if m and not re.search(r"\\frac\{d|'", cleaned):
        cleaned = m.group(1)
    parsed = _parse_derivative(cleaned)
    if parsed is None or parsed[0] is None or not isinstance(parsed[0], sp.Expr):
        return error_result(latex_expr)
    expr, var, order = parsed
    v = sp.latex(var)

    try:
        if expr.has(sp.Abs, sp.sign):
            # d|x|/dx is sign(x) over the reals; with a complex symbol SymPy returns re/im expressions
            real_var = sp.Symbol(var.name, real=True)
            result = sp.simplify(sp.diff(expr.xreplace({var: real_var}), real_var, order)).xreplace({real_var: var})
        else:
            result = sp.simplify(sp.diff(expr, var, order))
    except Exception:
        return error_result(latex_expr)

    op = f"\\frac{{d}}{{d{v}}}" if order == 1 else f"\\frac{{d^{{{order}}}}}{{d{v}^{{{order}}}}}"
    ordinal = {1: "", 2: "segunda ", 3: "tercera "}.get(order, f"{order}ª ")
    steps = [f"Calculamos la **{ordinal}derivada** de $${sp.latex(expr)}$$ con respecto a ${v}$."]

    rules = _derivative_rules(expr, var)
    if rules:
        steps.append("Reglas que aplican: " + "; ".join(rules) + ".")

    current = expr
    for k in range(1, order + 1):
        current = sp.simplify(sp.diff(current, var))
        if order > 1:
            steps.append(f"Derivada de orden {k}: $${sp.latex(current)}$$")

    factored = sp.factor(result)
    if order == 1:
        raw = sp.diff(expr, var)
        if sp.latex(raw) != sp.latex(result):
            steps.append(f"Derivando: $${sp.latex(raw)}$$")
            steps.append(f"Simplificamos: $${sp.latex(result)}$$")
    steps.append(f"**Resultado:** $${op}\\left({sp.latex(expr)}\\right) = {sp.latex(result)}$$")
    if factored != result and sp.count_ops(factored) < sp.count_ops(result):
        steps.append(f"Forma factorizada: $${sp.latex(factored)}$$")

    verified = _numeric_derivative_check(expr, var, order, result)
    if verified:
        steps.append("✓ Verificación numérica: la pendiente medida sobre la función en varios puntos "
                     "coincide con la derivada obtenida.")
    elif verified is False:
        logger.warning(f"Numeric check disagrees with derivative of {expr}: {result}")
        return {"symbolic": str(sp.Derivative(expr, (var, order))), "final_latex": r"\text{No se pudo verificar}",
                "steps": steps[:-1] + ["⚠ El cálculo simbólico y la verificación numérica no coinciden, "
                                       "así que no mostramos un resultado que podría ser incorrecto."],
                "answer": None, "verified": False, "show_graph": False}

    graph = None
    if expr.free_symbols == {var}:
        label = "f'(x)" if order == 1 else f"f^({order})(x)"
        graph = {"var": var, "curves": [{"expr": expr, "label": "f(x)"}, {"expr": result, "label": label}]}

    return {
        "symbolic": str(sp.Derivative(expr, (var, order))),
        "final_latex": sp.latex(result),
        "steps": steps,
        "answer": result,
        "verified": verified,
        "show_graph": graph is not None,
        "graph": graph,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LIMITS
# ─────────────────────────────────────────────────────────────────────────────

def _indeterminate_form(num, den, var, point, direction):
    try:
        ln = sp.limit(num, var, point, dir=direction)
        ld = sp.limit(den, var, point, dir=direction)
    except Exception:
        return None
    if ln == 0 and ld == 0:
        return r"\frac{0}{0}"
    if ln.is_infinite and ld.is_infinite:
        return r"\frac{\infty}{\infty}"
    return None


def solve_limit(latex_expr: str) -> dict:
    cleaned = clean_latex(latex_expr)
    parsed = parse_math(cleaned)
    if not isinstance(parsed, sp.Limit):
        return error_result(latex_expr, r"Ejemplo: `\lim_{x \to 0} \frac{\sin(x)}{x}`")

    expr, var, point = parsed.args[0], parsed.args[1], parsed.args[2]
    direction = str(parsed.args[3]) if len(parsed.args) > 3 else "+-"
    if direction not in ("+", "-", "+-"):
        direction = "+-"
    if point in (sp.oo, -sp.oo):
        direction = "-" if point == sp.oo else "+"
    v, p = sp.latex(var), sp.latex(point)
    side = {"+": "^{+}", "-": "^{-}"}.get(direction, "") if point not in (sp.oo, -sp.oo) else ""
    lim_l = f"\\lim_{{{v} \\to {p}{side}}} {sp.latex(expr)}"

    steps = [f"Queremos calcular: $${lim_l}$$"]

    direct = None
    try:
        if point.is_finite:
            direct = sp.simplify(expr.subs(var, point))
    except Exception:
        pass

    if direct is not None and direct.is_finite and direct is not sp.nan and not direct.has(sp.zoo):
        steps.append(f"Sustituimos directamente ${v} = {p}$: la función es continua allí.")
        result = direct
    else:
        num, den = sp.fraction(sp.together(expr))
        form = _indeterminate_form(num, den, var, point, direction) if den.has(var) else None
        if form:
            steps.append(f"Al sustituir obtenemos la **indeterminación** ${form}$.")
            factored = sp.cancel(expr)
            if factored != expr and sp.fraction(factored)[1] != den:
                steps.append(f"Factorizamos y simplificamos: $${sp.latex(factored)}$$")
            else:
                dn, dd = sp.diff(num, var), sp.diff(den, var)
                steps.append(
                    f"Aplicamos la **regla de L'Hôpital** (derivamos numerador y denominador): "
                    f"$${lim_l} = \\lim_{{{v} \\to {p}}} \\frac{{{sp.latex(dn)}}}{{{sp.latex(dd)}}}$$"
                )
        elif point in (sp.oo, -sp.oo):
            steps.append(f"Estudiamos el comportamiento cuando ${v} \\to {p}$, comparando los **órdenes de crecimiento**.")
        try:
            result = sp.limit(expr, var, point, dir=direction)
            if result == sp.zoo:
                raise ValueError("lateral limits differ")
        except ValueError:
            # Two-sided limit does not exist: show lateral limits
            left = sp.limit(expr, var, point, dir='-')
            right = sp.limit(expr, var, point, dir='+')
            steps.append(f"Límites laterales: $\\lim_{{{v}\\to {p}^-}} = {sp.latex(left)}$, $\\lim_{{{v}\\to {p}^+}} = {sp.latex(right)}$.")
            steps.append("Como los límites laterales son distintos, **el límite no existe**.")
            return {"symbolic": str(parsed), "final_latex": r"\text{No existe}", "steps": steps,
                    "answer": "no_existe", "show_graph": False}
        except Exception as e:
            logger.warning(f"limit failed: {e}")
            return error_result(latex_expr)

    verified = None
    if result.has(sp.AccumBounds):
        steps.append("La función oscila sin acercarse a un valor: **el límite no existe**.")
        final, answer = r"\text{No existe}", "no_existe"
    else:
        steps.append(f"**Resultado:** $${lim_l} = {sp.latex(result)}$$")
        final, answer = sp.latex(result), result
        verified = _numeric_limit_check(expr, var, point, direction, result)
        if verified:
            steps.append(f"✓ Verificación numérica: evaluando la función muy cerca de ${v} = {p}$ los valores se acercan a ${sp.latex(result)}$.")
        elif verified is False:
            logger.warning(f"Numeric check disagrees with limit {parsed} = {result}")
            return {"symbolic": str(parsed), "final_latex": r"\text{No se pudo verificar}",
                    "steps": steps[:-1] + ["⚠ El cálculo simbólico y la verificación numérica no coinciden, "
                                           "así que no mostramos un resultado que podría ser incorrecto."],
                    "show_graph": False, "ok": False}

    graph = None
    if expr.free_symbols == {var}:
        graph = {"var": var, "curves": [{"expr": expr, "label": "f(x)"}]}
        pf = _as_float(point)
        if pf is not None:
            graph["x_range"] = (pf - 5, pf + 5)
            rf = _as_float(result)
            if rf is not None:
                graph["points"] = [{"x": pf, "y": rf, "label": f"→ {sp.N(result, 4)}"}]

    return {
        "symbolic": str(parsed),
        "final_latex": final,
        "steps": steps,
        "answer": answer,
        "verified": verified,
        "show_graph": graph is not None,
        "graph": graph,
    }


_DERIVATIVE_PROBES = ("0.37", "0.81", "1.43", "2.29", "-0.58", "-1.67")


def _numeric_derivative_check(expr, var, order, result) -> bool | None:
    """
    Differentiate numerically (mpmath, 40 digits), without using SymPy's rules, and compare
    with the symbolic derivative at a few points where both are defined. The probes avoid
    integers and simple fractions, where singularities and kinks usually sit.
    """
    if expr.free_symbols != {var} or result.has(sp.Derivative) or not result.free_symbols <= {var}:
        return None
    import mpmath
    try:
        f = sp.lambdify(var, expr, "mpmath")
        df = sp.lambdify(var, result, "mpmath")
    except Exception:
        return None
    agree = 0
    with mpmath.workdps(40):
        for probe in _DERIVATIVE_PROBES:
            p = mpmath.mpf(probe)
            try:
                exact = mpmath.mpc(df(p))
                numeric = mpmath.mpc(mpmath.diff(f, p, order))
            except (ValueError, ZeroDivisionError, TypeError, OverflowError):
                continue  # outside the domain (ln of a negative, a pole): try another point
            if not (mpmath.isfinite(exact) and mpmath.isfinite(numeric)):
                continue
            if abs(exact - numeric) > mpmath.mpf("1e-12") * (1 + abs(exact)):
                return False
            agree += 1
    return True if agree >= 2 else None


def _numeric_limit_check(expr, var, point, direction, result) -> bool | None:
    """
    Evaluate the function ever closer to the point (80-digit arithmetic) and compare
    with the symbolic limit. Some limits converge very slowly (1/ln x), so instead of
    demanding closeness at one point it accepts an error that clearly shrinks.
    False means the numbers contradict the symbolic result.
    """
    if not (result.is_number and result.is_finite) or not point.is_number:
        return None
    scales = [sp.Integer(10) ** k for k in (6, 12, 24)]
    if point in (sp.oo, -sp.oo):
        sides = [[point / abs(point) * s for s in scales]]
    else:
        sides = [[point + sign / s for s in scales]
                 for sign in {"+": [1], "-": [-1]}.get(direction, [-1, 1])]
    target = complex(sp.N(result, 30))
    tol = 1e-6 * (1 + abs(target))
    for probes in sides:
        try:
            # evalf with a Float substitution: an exact (1 + 10^-24)^(10^24) would never finish
            errors = [abs(complex(expr.evalf(80, subs={var: sp.Float(p, 90)})) - target) for p in probes]
        except (TypeError, ValueError):
            return None
        if errors[-1] > tol and not errors[-1] < 0.75 * errors[0]:
            return False
    return True
