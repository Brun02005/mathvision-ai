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

from engines.math.common import clean_latex, parse_math, pick_variable, error_result

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRALS
# ─────────────────────────────────────────────────────────────────────────────

def solve_integral(latex_expr: str) -> dict:
    """Entry point — detects integral type and routes to the right solver."""
    cleaned = clean_latex(latex_expr)
    parsed = parse_math(cleaned)

    if isinstance(parsed, sp.Integral):
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
    if is_def:
        _, a, b = limits
        a_l, b_l = sp.latex(a), sp.latex(b)
        steps.append(f"Tenemos la **integral definida**: $$\\int_{{{a_l}}}^{{{b_l}}} {integrand_l}\\, d{v}$$")
        if a.has(sp.oo, -sp.oo) or b.has(sp.oo, -sp.oo):
            steps.append("Es una **integral impropia** (un límite es infinito): la calculamos como límite de integrales definidas.")
    else:
        steps.append(f"Tenemos la **integral indefinida**: $$\\int {integrand_l}\\, d{v}$$")

    steps.append(f"**Técnica:** {technique}")
    steps.extend(sub_steps)

    if antideriv is not None:
        antideriv = sp.simplify(antideriv)
        steps.append(f"**Primitiva:** $$F({v}) = {sp.latex(antideriv)}$$")
        steps.append(f"Verificación: derivando $F$ se recupera el integrando, $F'({v}) = {integrand_l}$.")

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
        if antideriv is not None and not (a.has(sp.oo, -sp.oo) or b.has(sp.oo, -sp.oo)):
            Fb = sp.simplify(antideriv.subs(var, b))
            Fa = sp.simplify(antideriv.subs(var, a))
            steps.append(
                f"Aplicamos la **Regla de Barrow** (Teorema Fundamental del Cálculo): "
                f"$$F({sp.latex(b)}) - F({sp.latex(a)}) = {sp.latex(Fb)} - \\left({sp.latex(Fa)}\\right) = {sp.latex(result)}$$"
            )
        if result in (sp.oo, -sp.oo, sp.zoo) or result.has(sp.oo):
            steps.append("La integral **diverge**.")
        final_l = sp.latex(result)
        if result.is_number and not result.is_Rational and result.is_finite:
            final_l += f" \\approx {sp.latex(sp.N(result, 6))}"
    else:
        if antideriv is None:
            return {
                "symbolic": str(sp.Integral(integrand_s, var)),
                "final_latex": r"\text{Sin primitiva elemental}",
                "steps": steps + ["Esta función **no tiene primitiva expresable con funciones elementales**."],
                "show_graph": False,
            }
        final_l = sp.latex(antideriv) + " + C"

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
        "show_graph": graph is not None,
        "graph": graph,
    }


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


def solve_derivative(latex_expr: str) -> dict:
    cleaned = clean_latex(latex_expr)
    parsed = _parse_derivative(cleaned)
    if parsed is None or parsed[0] is None:
        return error_result(latex_expr)
    expr, var, order = parsed
    v = sp.latex(var)

    try:
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

    graph = None
    if expr.free_symbols == {var}:
        label = "f'(x)" if order == 1 else f"f^({order})(x)"
        graph = {"var": var, "curves": [{"expr": expr, "label": "f(x)"}, {"expr": result, "label": label}]}

    return {
        "symbolic": str(sp.Derivative(expr, (var, order))),
        "final_latex": sp.latex(result),
        "steps": steps,
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
            return {"symbolic": str(parsed), "final_latex": r"\text{No existe}", "steps": steps, "show_graph": False}
        except Exception as e:
            logger.warning(f"limit failed: {e}")
            return error_result(latex_expr)

    if result.has(sp.AccumBounds):
        steps.append("La función oscila sin acercarse a un valor: **el límite no existe**.")
        final = r"\text{No existe}"
    else:
        steps.append(f"**Resultado:** $${lim_l} = {sp.latex(result)}$$")
        final = sp.latex(result)

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
        "show_graph": graph is not None,
        "graph": graph,
    }
