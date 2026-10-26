"""
Algebra solver — equations, inequalities, systems, numeric evaluation and
function analysis (f(x) = ...). Uses SymPy for exact symbolic computation.
"""
import re
import logging

import sympy as sp

from engines.math.common import (
    x, clean_latex, parse_math, split_top_level, pick_variable, error_result,
)

logger = logging.getLogger(__name__)

_FUNC_DEF = re.compile(r'^\s*([fghy])\s*(?:\(\s*([a-z])\s*\))?\s*$')
SEP = r",\; "
_INEQ = re.compile(r'\\leq?|\\geq?|\\le\b|\\ge\b|<|>|≤|≥')


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def solve_equation(latex_expr: str) -> dict:
    """
    Entry point for algebra. Routes to:
    systems (several equations) · inequalities · function analysis · equations · evaluation.
    """
    s = clean_latex(latex_expr)
    s = re.sub(r'\\begin\{(cases|array|aligned)\}(\{[^}]*\})?|\\end\{(cases|array|aligned)\}', '', s)

    parts = [p for p in split_top_level(s.replace(r'\\', ';'), seps=(';', ',')) if p]
    if len(parts) > 1 and all('=' in p for p in parts):
        return solve_system(parts)

    if _INEQ.search(s):
        return solve_inequality(s)

    if '=' in s:
        lhs_s, rhs_s = s.split('=', 1)
        m = _FUNC_DEF.match(lhs_s)
        if m:
            rhs = parse_math(rhs_s)
            if rhs is None:
                return error_result(latex_expr)
            var = sp.Symbol(m.group(2)) if m.group(2) else pick_variable(rhs)
            name = m.group(1)
            label = f"{name}({var})" if name != 'y' else 'y'
            return analyze_function(rhs, var, label)

        lhs, rhs = parse_math(lhs_s), parse_math(rhs_s)
        if lhs is None or rhs is None:
            return error_result(latex_expr)
        return _solve_single_equation(sp.Eq(lhs, rhs, evaluate=False))

    expr = parse_math(s)
    if expr is None or not isinstance(expr, sp.Basic):
        return error_result(latex_expr)
    if not expr.free_symbols:
        return evaluate_expression(expr)
    if len(expr.free_symbols) == 1:
        return analyze_function(expr, next(iter(expr.free_symbols)), "f(x)")
    return simplify_expression(expr)


# ─────────────────────────────────────────────────────────────────────────────
# EVALUATION / SIMPLIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def _with_decimal(val) -> str:
    """LaTeX of a value, plus a decimal approximation when it is not a simple rational."""
    val_l = sp.latex(val)
    try:
        if val.is_number and not val.is_Rational:
            approx = sp.N(val, 6)
            if approx.is_real:
                return f"{val_l} \\approx {sp.latex(approx)}"
    except Exception:
        pass
    return val_l


def evaluate_expression(expr) -> dict:
    val = sp.nsimplify(sp.simplify(expr.doit()), rational=False) if expr.has(sp.Float) else sp.simplify(expr.doit())
    steps = [f"Evaluamos la expresión: $${sp.latex(expr)}$$"]
    if expr.has(sp.Add) and any(t.is_Rational and not t.is_Integer for t in expr.atoms(sp.Rational)):
        steps.append("Llevamos las fracciones a **común denominador** y sumamos los numeradores.")
    steps.append(f"**Resultado:** $${_with_decimal(val)}$$")
    return {
        "symbolic": str(expr),
        "final_latex": sp.latex(val),
        "steps": steps,
        "show_graph": False,
    }


def simplify_expression(expr) -> dict:
    simp = sp.simplify(expr)
    fact = sp.factor(simp)
    steps = [f"Tenemos la expresión: $${sp.latex(expr)}$$",
             f"Simplificamos: $${sp.latex(simp)}$$"]
    if fact != simp:
        steps.append(f"Factorizamos: $${sp.latex(fact)}$$")
    return {"symbolic": str(expr), "final_latex": sp.latex(fact), "steps": steps, "show_graph": False}


# ─────────────────────────────────────────────────────────────────────────────
# EQUATIONS
# ─────────────────────────────────────────────────────────────────────────────

def _equation_type(poly_expr, var) -> tuple[str, int | None]:
    try:
        if poly_expr.is_polynomial(var):
            deg = sp.degree(poly_expr, var)
            names = {1: "ecuación lineal", 2: "ecuación cuadrática", 3: "ecuación cúbica"}
            return names.get(deg, f"ecuación polinomial de grado {deg}"), deg
    except Exception:
        pass
    if poly_expr.has(sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc):
        return "ecuación trigonométrica", None
    if poly_expr.has(sp.exp, sp.log) or any(b == sp.E for b, _ in [p.as_base_exp() for p in poly_expr.atoms(sp.Pow)]):
        return "ecuación exponencial/logarítmica", None
    if poly_expr.is_rational_function(var):
        return "ecuación racional", None
    return "ecuación", None


def _solve_single_equation(eq) -> dict:
    var = pick_variable(eq)
    expr = sp.simplify(eq.lhs - eq.rhs)
    eq_l = sp.latex(eq)
    var_l = sp.latex(var)

    if not eq.free_symbols:
        holds = sp.simplify(expr) == 0
        return {
            "symbolic": str(eq),
            "final_latex": r"\text{Verdadero}" if holds else r"\text{Falso}",
            "steps": [f"La igualdad no tiene variables: $${eq_l}$$",
                      "Ambos lados son iguales, la igualdad es **verdadera**." if holds
                      else "Los lados son distintos, la igualdad es **falsa**."],
            "show_graph": False,
        }

    tipo, degree = _equation_type(expr, var)
    steps = [f"Identificamos una **{tipo}** en ${var_l}$: $${eq_l}$$"]
    steps.append(f"Pasamos todo a un miembro: $${sp.latex(expr)} = 0$$")

    if degree == 1:
        a, b = sp.Poly(expr, var).all_coeffs()
        steps.append(f"Despejamos: $${sp.latex(a)}\\,{var_l} = {sp.latex(-b)} \\Rightarrow {var_l} = \\frac{{{sp.latex(-b)}}}{{{sp.latex(a)}}}$$")
    elif degree == 2:
        a, b, c = sp.Poly(expr, var).all_coeffs()
        disc = sp.simplify(b**2 - 4 * a * c)
        steps.append(f"Coeficientes: $a = {sp.latex(a)}$, $b = {sp.latex(b)}$, $c = {sp.latex(c)}$.")
        steps.append(f"Calculamos el discriminante: $$\\Delta = b^2 - 4ac = {sp.latex(disc)}$$")
        if disc.is_number:
            if disc > 0:
                steps.append("Como $\\Delta > 0$, hay **dos soluciones reales distintas**.")
            elif disc == 0:
                steps.append("Como $\\Delta = 0$, hay **una solución real doble**.")
            else:
                steps.append("Como $\\Delta < 0$, **no hay soluciones reales** (las soluciones son complejas conjugadas).")
        steps.append(r"Aplicamos la fórmula resolvente: $$" + var_l + r" = \frac{-b \pm \sqrt{\Delta}}{2a}$$")
    elif degree is not None and degree > 2:
        fact = sp.factor(expr)
        if fact != expr:
            steps.append(f"Factorizamos el polinomio: $${sp.latex(fact)} = 0$$")
            steps.append("Un producto es cero si alguno de sus factores es cero.")
    else:
        steps.append(f"Despejamos ${var_l}$ aplicando operaciones inversas a ambos miembros.")

    try:
        solutions = sp.solve(eq, var)
    except Exception as e:
        logger.warning(f"solve() failed: {e}")
        solutions = []

    if not solutions:
        try:
            solutions = [sp.nsolve(expr, var, 1)]
            steps.append("No hay solución cerrada; aproximamos numéricamente (método de Newton).")
        except Exception:
            pass

    real = [s for s in solutions if s.is_real is not False]
    complex_ = [s for s in solutions if s.is_real is False]

    if not solutions:
        return {
            "symbolic": str(eq),
            "final_latex": r"\text{Sin solución}",
            "steps": steps + ["No se encontraron soluciones para esta ecuación."],
            "show_graph": False,
        }

    if real:
        for i, s in enumerate(real, 1):
            label = f"**Solución {i}:**" if len(real) > 1 else "**Solución:**"
            steps.append(f"{label} $${var_l} = {_with_decimal(s)}$$")
        sols_l = [sp.latex(s) for s in real]
        final = (f"{var_l} = {sols_l[0]}" if len(sols_l) == 1
                 else f"{var_l} \\in \\left\\{{{SEP.join(sols_l)}\\right\\}}")
    else:
        final = r"\text{Sin solución real}"
        steps.append("La ecuación **no tiene soluciones reales**.")

    if complex_:
        steps.append("Soluciones complejas: $$" + ",\\quad ".join(f"{var_l} = {sp.latex(s)}" for s in complex_) + "$$")
        if not real:
            final = f"{var_l} \\in \\left\\{{{SEP.join(sp.latex(s) for s in complex_)}\\right\\}} \\subset \\mathbb{{C}}"

    # General solution for periodic equations
    if tipo == "ecuación trigonométrica":
        try:
            general = sp.solveset(expr, var, sp.S.Reals)
            if isinstance(general, (sp.Union, sp.ImageSet)):
                steps.append(f"Por periodicidad, la **solución general** es: $${var_l} \\in {sp.latex(general)}, \\; n \\in \\mathbb{{Z}}$$")
        except Exception:
            pass

    # Verification
    for s in real[:3]:
        try:
            if sp.simplify(expr.subs(var, s)) == 0:
                steps.append(f"✓ Verificación: al sustituir ${var_l} = {sp.latex(s)}$ la igualdad se cumple.")
        except Exception:
            pass

    graph = None
    if len(expr.free_symbols) == 1:
        points = []
        for s in real:
            try:
                points.append({"x": float(s), "y": 0, "label": f"{var}={sp.N(s, 3)}"})
            except Exception:
                pass
        graph = {"var": var, "curves": [{"expr": expr, "label": f"{sp.latex(expr)}"}],
                 "points": points, "x_range": _range_around([p["x"] for p in points])}
        graph["curves"][0]["label"] = "lado izq. − lado der."

    return {
        "symbolic": str(eq),
        "final_latex": final,
        "steps": steps,
        "show_graph": graph is not None,
        "graph": graph,
    }


def _range_around(xs: list, pad: float = 4.0, default=(-10, 10)):
    if not xs:
        return default
    lo, hi = min(xs), max(xs)
    span = max(hi - lo, 2.0)
    return (lo - span / 2 - pad / 2, hi + span / 2 + pad / 2)


# ─────────────────────────────────────────────────────────────────────────────
# INEQUALITIES
# ─────────────────────────────────────────────────────────────────────────────

def solve_inequality(s: str) -> dict:
    rel = parse_math(s)
    if rel is None or not isinstance(rel, sp.core.relational.Relational):
        return error_result(s)
    var = pick_variable(rel)
    try:
        sol_set = sp.solve_univariate_inequality(rel, var, relational=False)
    except Exception as e:
        logger.warning(f"inequality failed: {e}")
        return error_result(s)

    expr = sp.simplify(rel.lhs - rel.rhs)
    steps = [
        f"Tenemos la **inecuación**: $${sp.latex(rel)}$$",
        f"Pasamos todo a un miembro y comparamos con cero: $${sp.latex(expr)} \\;\\text{{vs}}\\; 0$$",
    ]
    try:
        crit = sorted(set(sp.solve(expr, var)), key=lambda v: float(v))
        crit = [c for c in crit if c.is_real]
        if crit:
            steps.append("Puntos críticos (donde la expresión vale cero): $$" +
                         ",\\; ".join(f"{sp.latex(var)} = {sp.latex(c)}" for c in crit) + "$$")
            steps.append("Analizamos el **signo** de la expresión en cada intervalo determinado por esos puntos.")
    except Exception:
        crit = []

    steps.append(f"**Conjunto solución:** $${sp.latex(var)} \\in {sp.latex(sol_set)}$$")
    graph = None
    if len(expr.free_symbols) == 1:
        graph = {"var": var, "curves": [{"expr": expr, "label": "lado izq. − lado der."}],
                 "points": [{"x": float(c), "y": 0, "label": ""} for c in crit],
                 "x_range": _range_around([float(c) for c in crit])}
    return {
        "symbolic": str(rel),
        "final_latex": f"{sp.latex(var)} \\in {sp.latex(sol_set)}",
        "steps": steps,
        "show_graph": graph is not None,
        "graph": graph,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEMS OF EQUATIONS
# ─────────────────────────────────────────────────────────────────────────────

def solve_system(parts: list[str]) -> dict:
    eqs = []
    for p in parts:
        lhs_s, rhs_s = p.split('=', 1)
        lhs, rhs = parse_math(lhs_s), parse_math(rhs_s)
        if lhs is None or rhs is None:
            return error_result('; '.join(parts))
        eqs.append(sp.Eq(lhs, rhs))

    variables = sorted(set().union(*(e.free_symbols for e in eqs)), key=lambda s: s.name)
    vars_l = ", ".join(sp.latex(v) for v in variables)
    system_l = r"\begin{cases} " + r" \\ ".join(sp.latex(e) for e in eqs) + r" \end{cases}"

    steps = [f"Tenemos un **sistema de {len(eqs)} ecuaciones** con incógnitas ${vars_l}$: $${system_l}$$"]

    is_linear = all(sp.Poly(e.lhs - e.rhs, *variables).is_linear for e in eqs
                    if (e.lhs - e.rhs).is_polynomial(*variables))
    if is_linear:
        A, b = sp.linear_eq_to_matrix([e.lhs - e.rhs for e in eqs], variables)
        steps.append("Es un **sistema lineal**. Lo escribimos en forma matricial $A\\vec{x} = \\vec{b}$:")
        steps.append(f"$$A = {sp.latex(A)},\\quad \\vec{{b}} = {sp.latex(b)}$$")
        aug = A.row_join(b)
        rref, _ = aug.rref()
        steps.append(f"Aplicamos **eliminación de Gauss-Jordan** sobre la matriz ampliada: $${sp.latex(aug)} \\sim {sp.latex(rref)}$$")
        rank_a, rank_ab = A.rank(), aug.rank()
        steps.append(f"Teorema de Rouché–Frobenius: $\\operatorname{{rg}}(A) = {rank_a}$, $\\operatorname{{rg}}(A|b) = {rank_ab}$, incógnitas $= {len(variables)}$.")
        if rank_a != rank_ab:
            steps.append("Como los rangos difieren, el sistema es **incompatible** (no tiene solución).")
            return {"symbolic": str(eqs), "final_latex": r"\text{Sistema incompatible}", "steps": steps, "show_graph": False}
        if rank_a < len(variables):
            steps.append("Rangos iguales pero menores que la cantidad de incógnitas: **compatible indeterminado** (infinitas soluciones).")
        else:
            steps.append("Rangos iguales a la cantidad de incógnitas: **compatible determinado** (solución única).")
    else:
        steps.append("El sistema es **no lineal**; lo resolvemos por **sustitución**.")

    try:
        sols = sp.solve(eqs, variables, dict=True)
    except Exception as e:
        logger.warning(f"system solve failed: {e}")
        sols = []

    if not sols:
        steps.append("No se encontraron soluciones.")
        return {"symbolic": str(eqs), "final_latex": r"\text{Sin solución}", "steps": steps, "show_graph": False}

    sol_ls = []
    for i, sol in enumerate(sols, 1):
        s_l = ",\\; ".join(f"{sp.latex(k)} = {sp.latex(v)}" for k, v in sol.items())
        sol_ls.append(s_l)
        steps.append(f"**Solución{' ' + str(i) if len(sols) > 1 else ''}:** $${s_l}$$")

    final = sol_ls[0] if len(sol_ls) == 1 else r" \;\lor\; ".join(f"({s})" for s in sol_ls)
    return {"symbolic": str(eqs), "final_latex": final, "steps": steps, "show_graph": False}


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def analyze_function(expr, var=x, label="f(x)") -> dict:
    """Study of a real function: domain, roots, intercept, critical points, extrema."""
    var_l = sp.latex(var)
    name = label.split('(')[0]
    steps = [f"Analizamos la función $${label} = {sp.latex(expr)}$$"]
    points = []
    summary = []

    try:
        dom = sp.calculus.util.continuous_domain(expr, var, sp.S.Reals)
        steps.append(f"**Dominio:** $$\\operatorname{{Dom}}({name}) = {sp.latex(dom)}$$")
    except Exception:
        dom = sp.S.Reals

    try:
        roots = sp.solveset(sp.Eq(expr, 0), var, dom)
        if isinstance(roots, sp.FiniteSet) and len(roots) <= 6:
            roots_l = ",\\; ".join(sp.latex(r) for r in roots) if roots else r"\varnothing"
            steps.append(f"**Raíces** (resolvemos ${label} = 0$): $${var_l} \\in \\left\\{{{roots_l}\\right\\}}$$" if roots
                         else "**Raíces:** la función no corta al eje $x$.")
            for r in roots:
                points.append({"x": float(r), "y": 0, "label": "raíz"})
            if roots:
                summary.append(f"\\text{{raíces: }} {roots_l}")
        elif roots != sp.S.EmptySet:
            steps.append(f"**Raíces:** $${var_l} \\in {sp.latex(roots)}$$")
    except Exception:
        pass

    try:
        if dom.contains(0) == sp.true:
            y0 = sp.simplify(expr.subs(var, 0))
            if y0.is_finite:
                steps.append(f"**Ordenada al origen:** ${name}(0) = {sp.latex(y0)}$")
                points.append({"x": 0, "y": float(y0), "label": "corte eje y"})
    except Exception:
        pass

    d1 = sp.simplify(sp.diff(expr, var))
    steps.append(f"**Derivada:** $${name}'({var_l}) = {sp.latex(d1)}$$")
    try:
        crit = sp.solveset(sp.Eq(d1, 0), var, dom)
        if isinstance(crit, sp.FiniteSet) and 0 < len(crit) <= 6:
            d2 = sp.diff(d1, var)
            steps.append(f"**Puntos críticos** (${name}'({var_l}) = 0$): $${var_l} \\in \\left\\{{{SEP.join(sp.latex(c) for c in crit)}\\right\\}}$$")
            for c in crit:
                yc = sp.simplify(expr.subs(var, c))
                sec = sp.simplify(d2.subs(var, c))
                kind = "mínimo relativo" if sec.is_positive else "máximo relativo" if sec.is_negative else "punto crítico (criterio no concluyente)"
                steps.append(f"En ${var_l} = {sp.latex(c)}$: ${name}''({sp.latex(c)}) = {sp.latex(sec)}$ ⇒ **{kind}** en $\\left({sp.latex(c)},\\; {sp.latex(yc)}\\right)$.")
                try:
                    points.append({"x": float(c), "y": float(yc), "label": kind.split(' ')[0]})
                except Exception:
                    pass
                summary.append(f"\\text{{{kind.split(' (')[0]} en }} ({sp.latex(c)},\\, {sp.latex(yc)})")
        elif crit == sp.S.EmptySet:
            steps.append("La derivada no se anula: **no hay extremos relativos**.")
    except Exception:
        pass

    xs = [p["x"] for p in points]
    graph = {"var": var, "curves": [{"expr": expr, "label": label}],
             "points": points, "x_range": _range_around(xs)}

    final = f"{label} = {sp.latex(expr)}"
    if summary:
        final = r"\begin{array}{l} " + r" \\ ".join(summary[:4]) + r" \end{array}"

    return {
        "symbolic": str(expr),
        "final_latex": final,
        "steps": steps,
        "show_graph": True,
        "graph": graph,
    }
