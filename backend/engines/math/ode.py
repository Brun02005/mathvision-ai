"""
Ordinary differential equations: classification (separable, linear, exact,
Bernoulli, constant coefficients...), general solution and initial value problems.

Accepted notation: y' = 2y · y'' + y = 0 · \\frac{dy}{dx} = xy · \\frac{d^2y}{dx^2} ...
with optional initial conditions separated by commas: y' = 2y, y(0) = 1
"""
import re
import logging

import sympy as sp

from engines.math.common import clean_latex, parse_math, split_top_level, error_result

logger = logging.getLogger(__name__)

_HINTS = {
    "separable": ("Ecuación de **variables separables**",
                  r"Separamos variables: $\frac{dy}{g(y)} = f(x)\,dx$ e integramos ambos miembros."),
    "1st_linear": ("Ecuación **lineal de primer orden**",
                   r"Escribimos $y' + P(x)\,y = Q(x)$ y multiplicamos por el **factor integrante** $\mu(x) = e^{\int P(x)\,dx}$."),
    "Bernoulli": ("Ecuación de **Bernoulli**",
                  r"Con el cambio $v = y^{1-n}$ la transformamos en una ecuación lineal."),
    "1st_exact": ("Ecuación **diferencial exacta**",
                  r"Verificamos $\frac{\partial M}{\partial y} = \frac{\partial N}{\partial x}$ y buscamos la función potencial $F(x,y)$."),
    "1st_homogeneous_coeff_best": ("Ecuación **homogénea**",
                                   r"Con el cambio $y = u\,x$ se reduce a variables separables."),
    "nth_linear_constant_coeff_homogeneous": ("Ecuación **lineal homogénea con coeficientes constantes**",
                                              r"Proponemos $y = e^{rx}$ y resolvemos la **ecuación característica**."),
    "nth_linear_constant_coeff_undetermined_coefficients": ("Ecuación **lineal no homogénea con coeficientes constantes**",
                                                            r"Solución general $y = y_h + y_p$: $y_h$ por la ecuación característica y $y_p$ por **coeficientes indeterminados**."),
    "nth_linear_constant_coeff_variation_of_parameters": ("Ecuación **lineal no homogénea con coeficientes constantes**",
                                                          r"Solución general $y = y_h + y_p$, con $y_p$ por **variación de parámetros**."),
    "nth_linear_euler_eq_homogeneous": ("Ecuación de **Euler–Cauchy**",
                                        r"Proponemos $y = x^r$ y resolvemos la ecuación indicial."),
    "factorable": ("Ecuación **factorizable**", "Factorizamos y resolvemos cada factor por separado."),
}

_IC = re.compile(r"^\s*([a-z])\s*('*)\s*\(\s*([^)]+)\s*\)\s*=\s*(.+)$")


def _normalize(s: str, dep: str) -> tuple[str, str]:
    """Rewrite Leibniz notation as primes. Returns (latex, independent variable)."""
    indep = "x"
    m = re.search(r"\\frac\{d\^?\{?\d*\}?\s*" + dep + r"\}\{d([a-z])", s)
    if m:
        indep = m.group(1)
    s = re.sub(r"\\frac\{d\^\{?3\}?\s*" + dep + r"\}\{d[a-z]\^\{?3\}?\}", dep + "'''", s)
    s = re.sub(r"\\frac\{d\^\{?2\}?\s*" + dep + r"\}\{d[a-z]\^\{?2\}?\}", dep + "''", s)
    s = re.sub(r"\\frac\{d\s*" + dep + r"\}\{d[a-z]\}", dep + "'", s)
    s = s.replace(r"^{\prime\prime}", "''").replace(r"^{\prime}", "'").replace(r"\prime", "'")
    return s, indep


def _detect_dependent(s: str) -> str:
    m = re.search(r"([a-z])\s*'", s) or re.search(r"\\frac\{d\^?\{?\d*\}?\s*([a-z])\}\{d", s)
    return m.group(1) if m else "y"


def _to_function(expr, dep: str, indep_sym):
    y = sp.Function(dep)(indep_sym)
    mapping = {sp.Symbol(dep + "'" * k): y.diff(indep_sym, k) for k in range(1, 5)}
    mapping[sp.Symbol(dep)] = y
    expr = expr.xreplace(mapping)
    # parse_latex reads \frac{dy}{dx} as Derivative(Symbol('y'), x): already handled above
    return expr, y


def solve_ode(latex_expr: str) -> dict:
    s = clean_latex(latex_expr)
    dep = _detect_dependent(s)
    s, indep = _normalize(s, dep)
    t = sp.Symbol(indep)

    parts = split_top_level(s, seps=(",", ";"))
    eq_part, ic_parts = parts[0], parts[1:]
    if "=" not in eq_part:
        eq_part += " = 0"
    lhs_s, rhs_s = eq_part.split("=", 1)
    lhs, rhs = parse_math(lhs_s), parse_math(rhs_s)
    if lhs is None or rhs is None:
        return error_result(latex_expr, "Ejemplo: `y' = 2y, y(0) = 1`  o  `y'' + y = 0`")

    lhs, y = _to_function(lhs, dep, t)
    rhs, _ = _to_function(rhs, dep, t)
    eq = sp.Eq(lhs, rhs)
    if not eq.has(sp.Derivative):
        return error_result(latex_expr, "No se encontró ninguna derivada de la función incógnita.")

    ics = {}
    for ic in ic_parts:
        m = _IC.match(ic)
        if not m:
            continue
        point, value = parse_math(m.group(3)), parse_math(m.group(4))
        order = len(m.group(2))
        if point is None or value is None:
            continue
        key = y.subs(t, point) if order == 0 else y.diff(t, order).subs(t, point)
        ics[key] = value

    order = sp.ode_order(eq, y)
    steps = [f"Tenemos la **ecuación diferencial ordinaria de orden {order}**: $${sp.latex(eq)}$$"]

    try:
        hints = sp.classify_ode(eq, y)
    except Exception:
        hints = ()
    hint_used = next((h for h in hints if h in _HINTS), None)
    if hint_used:
        title, method = _HINTS[hint_used]
        steps.append(f"La clasificamos como: {title}.")
        steps.append(method)
        if hint_used == "nth_linear_constant_coeff_homogeneous":
            r = sp.Symbol("r")
            expr = (eq.lhs - eq.rhs).expand()
            char = sum(expr.coeff(y.diff(t, k)) * r**k for k in range(1, order + 1)) + expr.coeff(y) * 1
            char = sp.expand(char.subs(y, 0))
            roots = sp.roots(sp.Poly(char, r))
            if roots:
                roots_l = ",\\; ".join(f"r = {sp.latex(k)}" + (f" \\;(\\text{{mult. }} {m})" if m > 1 else "")
                                       for k, m in roots.items())
                steps.append(f"Ecuación característica: $${sp.latex(char)} = 0 \\;\\Rightarrow\\; {roots_l}$$")

    try:
        sol = sp.dsolve(eq, y, ics=ics or None)
    except Exception as e:
        logger.warning(f"dsolve failed: {e}")
        try:
            sol = sp.dsolve(eq, y)
            if ics:
                steps.append("No se pudieron aplicar las condiciones iniciales; mostramos la solución general.")
                ics = {}
        except Exception as e2:
            logger.warning(f"dsolve (general) failed: {e2}")
            steps.append("SymPy no encontró una solución cerrada para esta ecuación.")
            return {"symbolic": str(eq), "final_latex": r"\text{Sin solución cerrada}", "steps": steps, "show_graph": False}

    sols = sol if isinstance(sol, list) else [sol]
    sol_ls = [sp.latex(s) for s in sols]
    if ics:
        conds = ",\\; ".join(f"{sp.latex(k)} = {sp.latex(v)}" for k, v in ics.items())
        steps.append(f"**Solución general** y luego aplicamos las condiciones iniciales ${conds}$ para hallar las constantes.")
    else:
        steps.append("Las constantes $C_1, C_2, \\dots$ son arbitrarias: obtenemos la **solución general** (familia de curvas).")
    for s_l in sol_ls:
        steps.append(f"$${s_l}$$")

    try:
        if all(sp.checkodesol(eq, s_)[0] for s_ in sols):
            steps.append("✓ Verificación: sustituyendo la solución en la ecuación, la igualdad se cumple.")
    except Exception:
        pass

    graph = None
    rhs_sol = sols[0].rhs
    consts = sorted((c for c in rhs_sol.free_symbols if c.name.startswith("C")), key=lambda c: c.name)
    if rhs_sol.free_symbols - set(consts) <= {t}:
        if not consts:
            graph = {"var": t, "curves": [{"expr": rhs_sol, "label": f"{dep}({indep})"}], "x_range": (-5, 5)}
        elif len(consts) <= 2:
            curves = []
            for cval in (-2, -1, 1, 2):
                curves.append({"expr": rhs_sol.subs({c: cval for c in consts}), "label": f"C = {cval}"})
            graph = {"var": t, "curves": curves, "x_range": (-5, 5)}

    return {
        "symbolic": str(eq),
        "final_latex": r" \\ ".join(sol_ls) if len(sol_ls) > 1 else sol_ls[0],
        "steps": steps,
        "show_graph": graph is not None,
        "graph": graph,
    }
