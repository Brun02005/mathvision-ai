"""
Algebra solver — equations, inequalities, systems, numeric evaluation and
function analysis (f(x) = ...). Uses SymPy for exact symbolic computation.
"""
import re
import logging

import sympy as sp

from engines.math import transform
from engines.math.common import (
    x, clean_latex, parse_math, split_top_level, pick_variable, error_result, unsolved_result, satisfies,
)

logger = logging.getLogger(__name__)

_FUNC_DEF = re.compile(r'^\s*([fghy])\s*(?:\(\s*([a-z])\s*\))?\s*$')
SEP = r",\; "
# (?![a-zA-Z]) so that \left is not read as \le
_INEQ = re.compile(r'\\(?:leq?|geq?|leqslant|geqslant|lt|gt)(?![a-zA-Z])|<|>|≤|≥')
_INEQ_SPLIT = re.compile(r'(\\(?:leq?|geq?|leqslant|geqslant|lt|gt)(?![a-zA-Z])|<=|>=|<|>|≤|≥)')
_REL = {"<": sp.Lt, "lt": sp.Lt, ">": sp.Gt, "gt": sp.Gt, "le": sp.Le, "leq": sp.Le, "leqslant": sp.Le,
        "<=": sp.Le, "≤": sp.Le, "ge": sp.Ge, "geq": sp.Ge, "geqslant": sp.Ge, ">=": sp.Ge, "≥": sp.Ge}


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
    # A bare expression with variables: like any calculator, show its simplest form
    # (plus factored / expanded forms). Function analysis is for "f(x) = ..." or "analizar".
    return transform.simplify(s)


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
    if val.has(sp.zoo, sp.nan) or val in (sp.oo, -sp.oo):
        return {"symbolic": str(expr), "final_latex": r"\text{Indefinido}",
                "steps": [f"Evaluamos la expresión: $${sp.latex(expr)}$$",
                          "Aparece una **división por cero** (o una función evaluada fuera de su dominio): "
                          "la expresión **no está definida**."],
                "answer": "indefinido", "show_graph": False}
    if val.has(sp.I):
        return _complex_result(expr, sp.expand_complex(val))
    steps = [f"Evaluamos la expresión: $${sp.latex(expr)}$$"]
    if expr.has(sp.Add) and any(t.is_Rational and not t.is_Integer for t in expr.atoms(sp.Rational)):
        steps.append("Llevamos las fracciones a **común denominador** y sumamos los numeradores.")
    steps.append(f"**Resultado:** $${_with_decimal(val)}$$")
    return {
        "symbolic": str(expr),
        "final_latex": sp.latex(val),
        "steps": steps,
        "answer": val,
        "show_graph": False,
    }


def _complex_result(expr, val) -> dict:
    re_, im_ = sp.re(val), sp.im(val)
    steps = [f"Operamos con **números complejos**, recordando que $i^2 = -1$: $${sp.latex(expr)}$$"]
    if expr.has(sp.Mul):
        steps.append("Aplicamos la propiedad distributiva y reemplazamos $i^2$ por $-1$.")
    if isinstance(expr, sp.Mul) and any(isinstance(f, sp.Pow) and f.exp == -1 for f in expr.args):
        steps.append("Para dividir, multiplicamos numerador y denominador por el **conjugado** del denominador.")
    steps.append(f"**Forma binómica:** $${sp.latex(val)}$$ (parte real ${sp.latex(re_)}$, parte imaginaria ${sp.latex(im_)}$)")
    modulus = sp.sqrt(re_**2 + im_**2)
    arg = sp.arg(val)
    steps.append(f"**Módulo:** $|z| = \\sqrt{{({sp.latex(re_)})^2 + ({sp.latex(im_)})^2}} = {_with_decimal(sp.simplify(modulus))}$")
    steps.append(f"**Argumento:** $\\arg z = {_with_decimal(sp.simplify(arg))}$ rad")
    steps.append(f"**Forma polar:** $z = {sp.latex(sp.simplify(modulus))}\\, e^{{i\\,{sp.latex(sp.simplify(arg))}}}$")
    steps.append(f"**Conjugado:** $\\bar{{z}} = {sp.latex(sp.conjugate(val))}$")
    return {"symbolic": str(expr), "final_latex": sp.latex(val), "steps": steps, "answer": val, "show_graph": False}


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

    if expr == 0:
        return _identity_result(eq, var)

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

    # Some equations are solved as SETS over the reals, because the answer can be an interval
    # (|x| + |x - 2| = 2 holds on all of [0, 2]) or empty (sin x = 2):
    # - absolute values (√(u²) is |u| over the reals);
    # - trig equations: principal solutions are those in [0, 2π), the general one comes later.
    real_var = sp.Symbol(var.name, real=True)
    expr_real = expr.xreplace({var: real_var})
    solution_set = None
    if expr_real.has(sp.Abs):
        steps.append("Por el **valor absoluto**, separamos en casos según el signo de su argumento "
                     r"($|u| = u$ si $u \geq 0$, $|u| = -u$ si $u < 0$).")
        solution_set = _safe_solveset(expr_real, real_var, sp.S.Reals)
    elif tipo == "ecuación trigonométrica":
        solution_set = _safe_solveset(expr_real, real_var, sp.Interval.Ropen(0, 2 * sp.pi))
        if isinstance(solution_set, sp.FiniteSet) and solution_set:
            steps.append(r"Buscamos primero las soluciones en una vuelta, $[0, 2\pi)$.")
    if solution_set is not None:
        solution_set = solution_set.xreplace({real_var: var})
    if solution_set == sp.S.EmptySet:
        reason = ("Las funciones seno y coseno solo toman valores entre $-1$ y $1$."
                  if tipo == "ecuación trigonométrica" and expr.has(sp.sin, sp.cos) else None)
        return {"symbolic": str(eq), "final_latex": r"\text{Sin solución real}",
                "steps": steps + ([reason] if reason else []) + ["La ecuación **no tiene soluciones reales**."],
                "answer": sp.S.EmptySet, "show_graph": False}
    if isinstance(solution_set, (sp.Interval, sp.Union)) or solution_set == sp.S.Reals:
        return _solution_set_result(eq, var, solution_set, steps)

    # sp.solve returning [] means "no solution"; raising means "SymPy could not decide".
    # Only the second case falls back to numeric roots, and they are reported as partial.
    try:
        if isinstance(solution_set, sp.FiniteSet):
            solutions = sorted(solution_set, key=lambda s: complex(s).real)
        else:
            solutions = [s.xreplace({real_var: var}) for s in sp.solve(expr_real if expr_real.has(sp.Abs) else eq,
                                                                         real_var if expr_real.has(sp.Abs) else var)]
    except Exception as e:
        logger.warning(f"solve() failed: {e}")
        solutions = _numeric_roots(expr, var)
        if not solutions:
            return unsolved_result(eq, steps, "SymPy no encontró una solución cerrada ni numérica para esta ecuación.")
        steps.append("No hay solución cerrada; **aproximamos numéricamente** (método de Newton desde varios puntos de partida). "
                     "Puede haber otras soluciones que este método no encuentra.")

    # Every candidate is checked against the ORIGINAL equation: this is what discards
    # extraneous solutions (log or root of a negative number, division by zero).
    checks = {}
    for s in solutions:
        checks[s] = satisfies(eq, {var: s})
    discarded = [s for s, ok in checks.items() if ok is False]
    for s in discarded:
        steps.append(f"Descartamos ${var_l} = {sp.latex(s)}$: no verifica la ecuación original (queda fuera del dominio).")
    solutions = [s for s in solutions if checks[s] is not False]
    verified = True if solutions and all(checks[s] is True for s in solutions) else None

    real = [s for s in solutions if s.is_real is not False]
    complex_ = [s for s in solutions if s.is_real is False]
    # Complex roots are part of the answer for polynomials (x² + 1 = 0) and when the variable is z.
    # For transcendental equations (e^x = -1) SymPy only returns SOME complex roots: listing them
    # would be incomplete, so we work over the reals.
    complex_mode = var.name == "z"
    if complex_ and degree is None and not complex_mode:
        complex_ = []
        solutions = real
        steps.append("Trabajamos en los números reales: descartamos las soluciones complejas.")
        if not real:
            return {"symbolic": str(eq), "final_latex": r"\text{Sin solución real}",
                    "steps": steps + ["La ecuación **no tiene soluciones reales**."],
                    "answer": sp.S.EmptySet, "show_graph": False}

    if not solutions:
        return {
            "symbolic": str(eq),
            "final_latex": r"\text{Sin solución}",
            "steps": steps + ["La ecuación **no tiene solución**."],
            "answer": sp.S.EmptySet,
            "show_graph": False,
        }

    if complex_mode and complex_:
        sols_l = [sp.latex(s) for s in solutions]
        steps.append("Soluciones en $\\mathbb{C}$: $$" + ",\\quad ".join(f"{var_l} = {s}" for s in sols_l) + "$$")
        final = f"{var_l} \\in \\left\\{{{SEP.join(sols_l)}\\right\\}}"
        real, complex_ = solutions, []
    elif real:
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

    if verified:
        shown = SEP.join(sp.latex(s) for s in solutions[:4])
        steps.append(f"✓ Verificación: sustituyendo ${var_l} = {shown}$ en la ecuación original, la igualdad se cumple.")

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
        "answer": sp.FiniteSet(*(real or complex_)),
        "verified": verified,
        "show_graph": graph is not None,
        "graph": graph,
    }


def _safe_solveset(expr, var, domain):
    """solveset, or None when it fails or only returns an unsolved ConditionSet."""
    try:
        result = sp.solveset(expr, var, domain)
    except Exception as e:
        logger.warning(f"solveset failed: {e}")
        return None
    return None if isinstance(result, sp.ConditionSet) else result


def _real_domain(eq, var):
    """Where both sides of the equation are defined as real numbers."""
    real_var = sp.Symbol(var.name, real=True)
    domain = sp.S.Reals
    for side in (eq.lhs, eq.rhs):
        try:
            domain = domain.intersect(sp.calculus.util.continuous_domain(side.xreplace({var: real_var}), real_var, sp.S.Reals))
        except Exception:
            pass
    return domain


def _identity_result(eq, var) -> dict:
    var_l = sp.latex(var)
    domain = _real_domain(eq, var)
    steps = [f"Tenemos: $${sp.latex(eq)}$$",
             "Al pasar todo a un miembro y simplificar queda $0 = 0$: es una **identidad**.",
             f"Se cumple para **todo** ${var_l}$ donde ambos miembros están definidos."]
    if domain != sp.S.Reals:
        steps.append(f"Los valores que anulan un denominador o salen del dominio quedan excluidos: $${var_l} \\in {sp.latex(domain)}$$")
    final = f"{var_l} \\in \\mathbb{{R}}" if domain == sp.S.Reals else f"{var_l} \\in {sp.latex(domain)}"
    return {"symbolic": str(eq), "final_latex": final, "steps": steps, "answer": domain,
            "verified": _check_inequality(eq, var, domain), "show_graph": False}


def _solution_set_result(eq, var, solution_set, steps) -> dict:
    """The equation holds on whole intervals (typical with absolute values)."""
    var_l = sp.latex(var)
    steps.append(f"La igualdad se cumple en todo un intervalo: $${var_l} \\in {sp.latex(solution_set)}$$")
    verified = _check_inequality(eq, var, solution_set)
    if verified:
        steps.append("✓ Verificación: probamos valores dentro y fuera del conjunto y la igualdad se cumple exactamente en él.")
    return {"symbolic": str(eq), "final_latex": f"{var_l} \\in {sp.latex(solution_set)}", "steps": steps,
            "answer": solution_set, "verified": verified, "show_graph": False}


def _numeric_roots(expr, var, starts=(-20, -5, -2, -0.5, 0.5, 2, 5, 20)) -> list:
    """Newton's method from several starting points; distinct real roots only."""
    roots = []
    for x0 in starts:
        try:
            r = sp.nsolve(expr, var, x0, prec=20)
        except Exception:
            continue
        if r.is_real and all(abs(r - other) > 1e-8 for other in roots):
            roots.append(sp.Float(r, 12))
    return sorted(roots)


def _range_around(xs: list, pad: float = 4.0, default=(-10, 10)):
    if not xs:
        return default
    lo, hi = min(xs), max(xs)
    span = max(hi - lo, 2.0)
    return (lo - span / 2 - pad / 2, hi + span / 2 + pad / 2)


# ─────────────────────────────────────────────────────────────────────────────
# INEQUALITIES
# ─────────────────────────────────────────────────────────────────────────────

def _solve_real_inequality(rel, var):
    """Solve over the reals (SymPy refuses |x| with a complex symbol)."""
    real_var = sp.Symbol(var.name, real=True)
    sol = sp.solve_univariate_inequality(rel.xreplace({var: real_var}), real_var, relational=False)
    return sol.xreplace({real_var: var})


def _solve_chained(parts: list[str], original: str) -> dict:
    """a < expr ≤ b means a < expr AND expr ≤ b."""
    a, op1, mid, op2, b = parts
    sides = [parse_math(p) for p in (a, mid, b)]
    if any(side is None for side in sides):
        return error_result(original)
    rel1 = _REL[op1.lstrip("\\")](sides[0], sides[1])
    rel2 = _REL[op2.lstrip("\\")](sides[1], sides[2])
    var = pick_variable(sides[1])
    try:
        sol = _solve_real_inequality(rel1, var).intersect(_solve_real_inequality(rel2, var))
    except Exception as e:
        logger.warning(f"chained inequality failed: {e}")
        return error_result(original)
    var_l = sp.latex(var)
    steps = [f"Es una **inecuación doble**: equivale a resolver a la vez $${sp.latex(rel1)} \\quad \\text{{y}} \\quad {sp.latex(rel2)}$$",
             f"Resolvemos cada una y nos quedamos con la **intersección**: $${var_l} \\in {sp.latex(sol)}$$"]
    verified = _check_inequality(sp.And(rel1, rel2), var, sol)
    if verified:
        steps.append("✓ Verificación: probamos valores de prueba dentro y fuera del conjunto.")
    return {"symbolic": f"{rel1} & {rel2}", "final_latex": f"{var_l} \\in {sp.latex(sol)}", "steps": steps,
            "answer": sol, "verified": verified, "show_graph": False}


def solve_inequality(s: str) -> dict:
    parts = _INEQ_SPLIT.split(clean_latex(s))
    if len(parts) == 5:
        return _solve_chained([p.strip() for p in parts], s)
    rel = parse_math(s)
    if rel in (sp.true, sp.false):
        # SymPy already decided it (|x| > -1 is always true): every real number, or none
        letters = re.findall(r'(?<![\\a-zA-Z])([a-z])(?![a-zA-Z])', clean_latex(s))
        var_l = letters[0] if letters else "x"
        holds = rel == sp.true
        return {"symbolic": s, "final_latex": f"{var_l} \\in " + (r"\mathbb{R}" if holds else r"\varnothing"),
                "steps": [f"Tenemos la **inecuación**: $${clean_latex(s)}$$",
                          "La desigualdad se cumple **para todo número real**, sin importar el valor de la variable "
                          "(por ejemplo, un valor absoluto nunca es negativo)." if holds else
                          "La desigualdad **no se cumple para ningún número real**."],
                "answer": sp.S.Reals if holds else sp.S.EmptySet, "show_graph": False}
    if rel is None or not isinstance(rel, sp.core.relational.Relational):
        return error_result(s)
    var = pick_variable(rel)
    try:
        sol_set = _solve_real_inequality(rel, var)
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
    verified = _check_inequality(rel, var, sol_set)
    if verified:
        steps.append("✓ Verificación: probamos valores de prueba dentro y fuera del conjunto y la desigualdad se cumple exactamente en él.")
    graph = None
    if len(expr.free_symbols) == 1:
        graph = {"var": var, "curves": [{"expr": expr, "label": "lado izq. − lado der."}],
                 "points": [{"x": float(c), "y": 0, "label": ""} for c in crit],
                 "x_range": _range_around([float(c) for c in crit])}
    return {
        "symbolic": str(rel),
        "final_latex": f"{sp.latex(var)} \\in {sp.latex(sol_set)}",
        "steps": steps,
        "answer": sol_set,
        "verified": verified,
        "show_graph": graph is not None,
        "graph": graph,
    }


def _check_inequality(rel, var, sol_set) -> bool | None:
    """Test points on a grid (and next to each boundary): the inequality must hold exactly inside the set."""
    probes = [sp.Rational(k, 4) for k in range(-80, 81, 3)]
    for b in sol_set.boundary if isinstance(sol_set, sp.Set) else []:
        if b.is_real and b.is_finite:
            probes += [b - sp.Rational(1, 1000), b + sp.Rational(1, 1000)]
    checked = 0
    for p in probes:
        try:
            holds = rel.subs(var, p)
            if holds not in (sp.true, sp.false):
                continue
            if bool(holds) != bool(sol_set.contains(p)):
                return False
            checked += 1
        except Exception:
            continue
    return True if checked >= 10 else None


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
            return {"symbolic": str(eqs), "final_latex": r"\text{Sistema incompatible}", "steps": steps,
                    "answer": sp.S.EmptySet, "verified": True, "show_graph": False}
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
        return unsolved_result(eqs, steps, "SymPy no pudo resolver este sistema.")

    if not is_linear and sols:
        real_sols = [sol for sol in sols if all(v.is_real is not False for v in sol.values())]
        if len(real_sols) < len(sols):
            complex_l = r" \;\lor\; ".join("(" + ",\\; ".join(f"{sp.latex(k)} = {sp.latex(v)}" for k, v in sol.items()) + ")"
                                         for sol in sols if sol not in real_sols)
            steps.append(f"Descartamos las soluciones complejas (trabajamos en los reales): $${complex_l}$$")
            if not real_sols:
                steps.append("El sistema **no tiene solución real**.")
                return {"symbolic": str(eqs), "final_latex": r"\text{Sin solución real}", "steps": steps,
                        "answer": sp.S.EmptySet, "show_graph": False}
        sols = real_sols

    if not sols:
        steps.append("El sistema **no tiene solución**.")
        return {"symbolic": str(eqs), "final_latex": r"\text{Sin solución}", "steps": steps,
                "answer": sp.S.EmptySet, "show_graph": False}

    sol_ls = []
    for i, sol in enumerate(sols, 1):
        s_l = ",\\; ".join(f"{sp.latex(k)} = {sp.latex(v)}" for k, v in sol.items())
        sol_ls.append(s_l)
        steps.append(f"**Solución{' ' + str(i) if len(sols) > 1 else ''}:** $${s_l}$$")

    checks = [satisfies(e, sol) for sol in sols for e in eqs]
    verified = True if all(c is True for c in checks) else None
    if verified:
        steps.append("✓ Verificación: los valores hallados cumplen todas las ecuaciones del sistema.")
    final = sol_ls[0] if len(sol_ls) == 1 else r" \;\lor\; ".join(f"({s})" for s in sol_ls)
    return {"symbolic": str(eqs), "final_latex": final, "steps": steps,
            "answer": sols[0] if len(sols) == 1 else sols, "verified": verified, "show_graph": False}


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def analyze(latex_expr: str) -> dict:
    """Explicit 'analizar': accepts `f(x) = ...` or a bare expression."""
    s = clean_latex(latex_expr)
    if '=' in s and _FUNC_DEF.match(s.split('=', 1)[0]):
        return solve_equation(s)
    expr = parse_math(s)
    if expr is None or not isinstance(expr, sp.Expr) or not expr.free_symbols:
        return error_result(latex_expr, "Ejemplo: `f(x) = x^3 - 3x`")
    return analyze_function(expr, pick_variable(expr), "f(x)")


_MAX_POINTS = 12


def _point_list(s) -> list | None:
    """Real points of a set, sorted; None when there are infinitely many or they cannot be ordered."""
    if s == sp.S.EmptySet:
        return []
    if not isinstance(s, sp.FiniteSet) or len(s) > _MAX_POINTS:
        return None
    try:
        return sorted((p for p in s if p.is_real is not False), key=float)
    except TypeError:
        return None


def _sample(a, b):
    """A point strictly inside (a, b) to test signs with."""
    if a == -sp.oo and b == sp.oo:
        return sp.Integer(0)
    if a == -sp.oo:
        return b - 1
    if b == sp.oo:
        return a + 1
    return (a + b) / 2


def _sign_at(g, var, point) -> int | None:
    try:
        v = sp.N(g.subs(var, point))
    except Exception:
        return None
    if not v.is_real:
        return None
    return 1 if v > 0 else -1 if v < 0 else 0


def _sign_table(g, var, dom):
    """
    Split `dom` at the zeros and singularities of g and return [(interval, sign)] in order,
    plus the cut points. None when g has infinitely many zeros there (it cannot be tabulated).
    """
    try:
        g_dom = sp.calculus.util.continuous_domain(g, var, dom)
    except Exception:
        g_dom = dom  # SymPy cannot tell where sign(x) (the derivative of |x|) jumps
    try:
        cuts = _point_list(g_dom.boundary)
        zeros = _point_list(sp.solveset(sp.Eq(g, 0), var, g_dom))
        # |u| and sign(u) change formula where u = 0
        kinks = [_point_list(sp.solveset(sp.Eq(a.args[0], 0), var, dom)) for a in g.atoms(sp.Abs, sp.sign)]
    except Exception:
        return None
    if cuts is None or zeros is None or None in kinks:
        return None
    cuts = sorted(set(cuts) | set(zeros) | {k for ks in kinks for k in ks}, key=float)
    edges = [-sp.oo, *cuts, sp.oo]
    table = []
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        t = _sample(a, b)
        if g_dom.contains(t) != sp.true:
            continue
        sign = _sign_at(g, var, t)
        if sign is None:
            return None
        table.append((sp.Interval.open(a, b), sign))
    return table, cuts


def _union(table, sign, join_through=None):
    """
    Union of the pieces with the given sign. With `join_through` (the function's domain), two
    neighbouring pieces with the same sign are joined through their common point when the
    function is defined there: x³ is increasing on all of ℝ, not on (-∞, 0) ∪ (0, ∞).
    """
    pieces = []
    for iv, s in table:
        if s != sign:
            continue
        prev = pieces[-1] if pieces else None
        if (prev is not None and join_through is not None and prev.end == iv.start
                and join_through.contains(iv.start) == sp.true):
            pieces[-1] = sp.Interval(prev.start, iv.end, prev.left_open, True)
        else:
            pieces.append(iv)
    return sp.Union(*pieces) if pieces else sp.S.EmptySet


def _neighbours(table, c):
    """Signs just left and right of the point c in a sign table."""
    left = next((s for iv, s in table if iv.end == c), None)
    right = next((s for iv, s in table if iv.start == c), None)
    return left, right


def _finite(v) -> bool:
    return (v is not None and not isinstance(v, sp.AccumBounds) and v.is_real is True
            and v.is_finite is True)


def _infinite(v) -> bool:
    return v in (sp.oo, -sp.oo, sp.zoo)


def _is_the_line(expr, var, line, end) -> bool:
    """
    True when, far towards `end`, the function coincides with the line instead of approaching it
    ((x²-1)/(x-1) is x+1 with a hole, |x| is x for x > 0): then the line is the graph, not an asymptote.
    """
    side = 1 if end == sp.oo else -1
    try:
        return all(sp.simplify((expr - line).subs(var, side * 10**k)) == 0 for k in (1, 2, 3))
    except Exception:
        return False


def _parity(expr, var) -> str:
    r = sp.Symbol(var.name, real=True)
    f = expr.subs(var, r)
    mirrored = f.subs(r, -r)
    try:
        if sp.simplify(mirrored - f) == 0:
            return "par"
        if sp.simplify(mirrored + f) == 0:
            return "impar"
    except Exception:
        pass
    return "ninguna"


def _set_latex(s):
    return r"\varnothing" if s == sp.S.EmptySet else sp.latex(s)


def analyze_function(expr, var=x, label="f(x)") -> dict:
    """
    Complete study of a real function, as it is done in class: domain, parity, intercepts,
    continuity, asymptotes, monotonicity and extrema, concavity and inflection points,
    sign (C⁺ / C⁻) and range. Periodic functions are studied over one period.
    """
    # A real variable: otherwise d|x|/dx comes out in terms of re(x) and im(x)
    given_var, var = var, sp.Symbol(var.name, real=True)
    expr = expr.subs(given_var, var)
    var_l = sp.latex(var)
    name = label.split('(')[0]
    steps = [f"Hacemos el **análisis completo** de $${label} = {sp.latex(expr)}$$"]
    points = []
    summary = []
    info = {"maxima": [], "minima": [], "inflection": [], "vertical_asymptotes": []}
    limits = {}

    def lim(point, direction="+-"):
        key = (point, direction)
        if key not in limits:
            try:
                limits[key] = sp.limit(expr, var, point, direction)
            except Exception:
                limits[key] = None
        return limits[key]

    def value(c):
        return sp.simplify(expr.subs(var, c))

    def add_point(px, py, text):
        try:
            points.append({"x": float(px), "y": float(py), "label": text})
        except (TypeError, ValueError):
            pass

    # 1. Domain
    try:
        dom = sp.calculus.util.continuous_domain(expr, var, sp.S.Reals)
    except Exception:
        dom = sp.S.Reals
    steps.append(f"**1. Dominio:** $$\\operatorname{{Dom}}({name}) = {sp.latex(dom)}$$")
    summary.append(f"\\text{{Dominio: }} {sp.latex(dom)}")

    # Periodic functions have infinitely many roots and extrema: study one period
    period = None
    try:
        period = sp.periodicity(expr, var)
    except Exception:
        pass
    work = dom
    if period is not None and period.is_positive:
        try:
            work = sp.calculus.util.continuous_domain(expr, var, sp.Interval(0, period))
        except Exception:
            work = sp.Intersection(dom, sp.Interval(0, period))
        steps.append(f"La función es **periódica** de período $T = {sp.latex(period)}$: estudiamos un período, "
                     f"$[0,\\, {sp.latex(period)}]$, y el resto se repite igual cada ${sp.latex(period)}$.")

    # 2. Parity
    parity = _parity(expr, var)
    info["parity"] = parity
    parity_text = {
        "par": f"${name}(-{var_l}) = {name}({var_l})$ ⇒ la función es **par** (simétrica respecto del eje $y$).",
        "impar": f"${name}(-{var_l}) = -{name}({var_l})$ ⇒ la función es **impar** (simétrica respecto del origen).",
        "ninguna": f"${name}(-{var_l})$ no es ${name}({var_l})$ ni $-{name}({var_l})$ ⇒ **no es par ni impar**.",
    }[parity]
    steps.append(f"**2. Paridad:** {parity_text}")

    # 3. Intercepts
    try:
        roots = sp.solveset(sp.Eq(expr, 0), var, dom)
    except Exception:
        roots = None
    info["roots"] = roots
    root_list = _point_list(roots) if roots is not None else None
    if root_list is not None:
        roots_l = SEP.join(sp.latex(r) for r in root_list)
        if root_list:
            steps.append(f"**3. Raíces** (resolvemos ${label} = 0$): $${var_l} \\in \\left\\{{{roots_l}\\right\\}}$$")
            summary.append(f"\\text{{Raíces: }} {roots_l}")
            for r in root_list:
                add_point(r, 0, "raíz")
        else:
            steps.append("**3. Raíces:** la función no corta al eje $x$.")
    elif roots is not None:
        steps.append(f"**3. Raíces:** $${var_l} \\in {sp.latex(roots)}$$")
    try:
        if dom.contains(0) == sp.true:
            y0 = value(0)
            if y0.is_finite:
                steps.append(f"**Ordenada al origen:** ${name}(0) = {sp.latex(y0)}$, el gráfico corta al eje $y$ en $(0,\\, {sp.latex(y0)})$.")
                add_point(0, y0, "corte eje y")
        else:
            steps.append(f"**Ordenada al origen:** $0 \\notin \\operatorname{{Dom}}({name})$, no corta al eje $y$.")
    except Exception:
        pass

    # 4. Continuity and vertical asymptotes: the points where the domain is interrupted
    continuity = []
    try:
        ends = _point_list(work.boundary) or []
    except Exception:
        ends = []
    # `work`, not `dom`: SymPy cannot always decide membership in the infinite domain of tan(x)
    gaps = [c for c in ends if work.contains(c) != sp.true]
    for c in gaps:
        sides = [d for d, t in (("-", c - sp.Rational(1, 10**6)), ("+", c + sp.Rational(1, 10**6)))
                 if work.contains(t) == sp.true]
        lims = {d: lim(c, d) for d in sides}
        c_l = sp.latex(c)
        if any(_infinite(v) for v in lims.values()):
            info["vertical_asymptotes"].append(c)
            detail = SEP.join(f"\\lim_{{{var_l} \\to {c_l}^{{{d}}}}} {name}({var_l}) = {sp.latex(v)}"
                              for d, v in lims.items() if v is not None)
            continuity.append(f"En ${var_l} = {c_l}$ la función no está definida y $${detail}$$ ⇒ **asíntota vertical** $x = {c_l}$.")
        elif len(lims) == 2 and all(_finite(v) for v in lims.values()):
            left, right = lims["-"], lims["+"]
            if sp.simplify(left - right) == 0:
                continuity.append(f"En ${var_l} = {c_l}$ hay una **discontinuidad evitable**: el límite existe y vale "
                                  f"${sp.latex(left)}$, pero la función no está definida ahí (agujero en $({c_l},\\, {sp.latex(left)})$).")
                summary.append(f"\\text{{Discontinuidad evitable en }} {var_l} = {c_l}")
            else:
                continuity.append(f"En ${var_l} = {c_l}$ hay una **discontinuidad de salto**: por izquierda tiende a "
                                  f"${sp.latex(left)}$ y por derecha a ${sp.latex(right)}$.")
                summary.append(f"\\text{{Salto en }} {var_l} = {c_l}")
    if continuity:
        steps.append("**4. Continuidad:** la función es continua en todo su dominio; miramos los puntos donde se interrumpe.")
        steps += continuity
    else:
        steps.append("**4. Continuidad:** la función es continua en todo su dominio y no tiene asíntotas verticales.")

    # 5. Horizontal and oblique asymptotes (behaviour at ±∞)
    at_infinity = []
    asymptotes = [f"x = {sp.latex(c)}" for c in info["vertical_asymptotes"]]
    info["horizontal_asymptotes"] = []
    info["oblique_asymptotes"] = []
    try:
        unbounded = {sp.oo: dom.sup == sp.oo, -sp.oo: dom.inf == -sp.oo}
    except Exception:
        unbounded = {}
    if period is None:
        for end, end_l in ((sp.oo, r"+\infty"), (-sp.oo, r"-\infty")):
            if not unbounded.get(end):
                continue
            at_end = lim(end, "-" if end == sp.oo else "+")
            if _finite(at_end) and _is_the_line(expr, var, at_end, end):
                at_infinity.append(f"Hacia ${end_l}$ la función **es** constante, $y = {sp.latex(at_end)}$: "
                                   f"es el propio gráfico, no una asíntota.")
            elif _finite(at_end):
                if at_end not in info["horizontal_asymptotes"]:
                    info["horizontal_asymptotes"].append(at_end)
                at_infinity.append(f"$$\\lim_{{{var_l} \\to {end_l}}} {name}({var_l}) = {sp.latex(at_end)}$$ ⇒ **asíntota horizontal** "
                             f"$y = {sp.latex(at_end)}$ hacia ${end_l}$.")
                asymptotes.append(f"y = {sp.latex(at_end)}")
            elif _infinite(at_end):
                try:
                    m = sp.limit(expr / var, var, end)
                    b = sp.limit(expr - m * var, var, end) if _finite(m) and m != 0 else None
                except Exception:
                    m = b = None
                line = sp.expand(m * var + b) if _finite(b) else None
                if line is not None and _is_the_line(expr, var, line, end):
                    at_infinity.append(f"Hacia ${end_l}$ el gráfico **es** la recta $y = {sp.latex(line)}$, "
                                       f"así que no hay asíntota de ese lado.")
                elif line is not None:
                    if line not in info["oblique_asymptotes"]:
                        info["oblique_asymptotes"].append(line)
                    at_infinity.append(f"Hacia ${end_l}$ la función no tiene límite finito. Buscamos asíntota oblicua $y = mx + b$: "
                                       f"$m = \\lim {name}({var_l})/{var_l} = {sp.latex(m)}$, "
                                       f"$b = \\lim ({name}({var_l}) - m{var_l}) = {sp.latex(b)}$ ⇒ **asíntota oblicua** "
                                       f"$y = {sp.latex(line)}$.")
                    asymptotes.append(f"y = {sp.latex(line)}")
                else:
                    at_infinity.append(f"$$\\lim_{{{var_l} \\to {end_l}}} {name}({var_l}) = {sp.latex(at_end)}$$ "
                                       f"y no se acerca a ninguna recta: no hay asíntota horizontal ni oblicua hacia ${end_l}$.")
    asymptotes = list(dict.fromkeys(asymptotes))
    if asymptotes:
        summary.append(r"\text{Asíntotas: }" + SEP.join(asymptotes))
    steps.append("**5. Asíntotas:** " + (f"$${SEP.join(asymptotes)}$$" if asymptotes else "no tiene."))
    steps += at_infinity

    # 6. Monotonicity and extrema (first-derivative test)
    d1 = sp.simplify(sp.diff(expr, var))
    steps.append(f"**6. Crecimiento y extremos.** Derivamos: $${name}'({var_l}) = {sp.latex(d1)}$$")
    mono = _sign_table(d1, var, work) if d1 != 0 else None
    if d1 == 0:
        steps.append("La derivada es $0$: la función es **constante**, no crece ni decrece.")
    elif mono is None:
        steps.append(f"No pudimos tabular el signo de ${name}'$ en forma exacta.")
    else:
        table, cuts = mono
        # The ends of the studied interval are not critical points (a period's ends, √x at 0)
        crit = [c for c in cuts if work.contains(c) == sp.true and c not in ends]
        if crit:
            steps.append(f"Puntos críticos (donde ${name}' = 0$ o no existe): $${var_l} \\in \\left\\{{{SEP.join(sp.latex(c) for c in crit)}\\right\\}}$$")
        up, down = _union(table, 1, work), _union(table, -1, work)
        info["increasing"], info["decreasing"] = up, down
        steps.append(f"Probando el signo de ${name}'$ en cada intervalo: **crece** en ${_set_latex(up)}$ "
                     f"y **decrece** en ${_set_latex(down)}$.")
        for c in crit:
            left, right = _neighbours(table, c)
            kind = ("máximo" if (left, right) == (1, -1) else "mínimo" if (left, right) == (-1, 1) else None)
            if kind is None:
                continue
            yc = value(c)
            info["maxima" if kind == "máximo" else "minima"].append(c)
            change = "pasa de crecer a decrecer" if kind == "máximo" else "pasa de decrecer a crecer"
            steps.append(f"En ${var_l} = {sp.latex(c)}$ la función {change} ⇒ **{kind} relativo** en "
                         f"$\\left({sp.latex(c)},\\; {sp.latex(yc)}\\right)$.")
            add_point(c, yc, kind)
            summary.append(f"\\text{{{kind.capitalize()}: }} ({sp.latex(c)},\\, {sp.latex(yc)})")
        if not info["maxima"] and not info["minima"]:
            steps.append("No hay extremos relativos.")

    # 7. Concavity and inflection points
    # The DiracDelta from differentiating sign(x) only lives at the kink, where f'' does not exist anyway
    d2 = sp.simplify(sp.diff(d1, var).replace(lambda e: isinstance(e, sp.DiracDelta), lambda e: sp.S.Zero))
    steps.append(f"**7. Concavidad.** Derivada segunda: $${name}''({var_l}) = {sp.latex(d2)}$$")
    conc = _sign_table(d2, var, work) if d2 != 0 else None
    if d2 == 0:
        steps.append("La derivada segunda es $0$: el gráfico es recto (por tramos), sin concavidad ni puntos de inflexión.")
    elif conc is None:
        steps.append(f"No pudimos tabular el signo de ${name}''$ en forma exacta.")
    else:
        table, cuts = conc
        cup, cap = _union(table, 1, work), _union(table, -1, work)
        info["concave_up"], info["concave_down"] = cup, cap
        steps.append(f"**Cóncava hacia arriba** ($\\cup$, ${name}'' > 0$) en ${_set_latex(cup)}$ y "
                     f"**cóncava hacia abajo** ($\\cap$, ${name}'' < 0$) en ${_set_latex(cap)}$.")
        for c in cuts:
            left, right = _neighbours(table, c)
            if work.contains(c) != sp.true or left is None or right is None or left * right >= 0:
                continue
            yc = value(c)
            info["inflection"].append(c)
            steps.append(f"En ${var_l} = {sp.latex(c)}$ cambia la concavidad ⇒ **punto de inflexión** "
                         f"$\\left({sp.latex(c)},\\; {sp.latex(yc)}\\right)$.")
            add_point(c, yc, "inflexión")
        if info["inflection"]:
            summary.append(r"\text{Inflexión: }" + SEP.join(
                f"({sp.latex(c)},\\, {sp.latex(value(c))})" for c in info["inflection"]))
        else:
            steps.append("No hay puntos de inflexión.")

    # 8. Sign: where the graph is above or below the x axis
    sign = _sign_table(expr, var, work)
    if sign is not None:
        pos, neg = _union(sign[0], 1), _union(sign[0], -1)
        info["positive"], info["negative"] = pos, neg
        steps.append(f"**8. Positividad y negatividad:** $$C^{{+}} = {_set_latex(pos)} \\qquad C^{{-}} = {_set_latex(neg)}$$")

    # 9. Range: on each interval where it is monotonic the function sweeps everything between
    # its values (or limits) at the ends, because it is continuous there
    image = None
    if d1 == 0:
        # Constant on each piece of the domain (|x|/x): one value per piece
        pieces = work.args if isinstance(work, sp.Union) else (work,)
        try:
            image = sp.Union(*(sp.FiniteSet(value(_sample(p.inf, p.sup))) for p in pieces))
        except Exception:
            image = None
    elif mono is not None:
        try:
            parts = []
            for iv, s in mono[0]:
                a_val, b_val = lim(iv.start, "+"), lim(iv.end, "-")
                if s == 0:
                    parts.append(sp.FiniteSet(value(_sample(iv.start, iv.end))))
                    continue
                if any(v is None or isinstance(v, sp.AccumBounds) or v.is_real is False for v in (a_val, b_val)):
                    raise ValueError("límite no determinado")
                lo, hi = (a_val, b_val) if s == 1 else (b_val, a_val)
                parts.append(sp.Interval.open(lo, hi))
            parts += [sp.FiniteSet(value(c)) for c in mono[1] if work.contains(c) == sp.true]
            image = sp.Union(*parts) if parts else None
        except Exception:
            image = None
    if image is None:
        try:
            image = sp.calculus.util.function_range(expr, var, work)
        except Exception:
            image = None
    if image is not None:
        info["range"] = image
        steps.append(f"**9. Imagen:** $$\\operatorname{{Im}}({name}) = {sp.latex(image)}$$")
        summary.append(f"\\text{{Imagen: }} {sp.latex(image)}")

    xs = [p["x"] for p in points] + [float(c) for c in info["vertical_asymptotes"] if c.is_real]
    graph = {"var": var, "curves": [{"expr": expr, "label": label}],
             "points": points, "x_range": _range_around(xs)}
    for line in info["horizontal_asymptotes"] + info["oblique_asymptotes"]:
        graph["curves"].append({"expr": line, "label": f"asíntota y = {sp.sstr(line)}"})
    graph["vlines"] = [{"x": c, "label": f"asíntota x = {sp.sstr(c)}"} for c in info["vertical_asymptotes"]]

    final = r"\begin{array}{l} " + r" \\ ".join(summary) + r" \end{array}"
    info.update(domain=dom, maxima=sp.FiniteSet(*info["maxima"]), minima=sp.FiniteSet(*info["minima"]),
                inflection=sp.FiniteSet(*info["inflection"]),
                vertical_asymptotes=sp.FiniteSet(*info["vertical_asymptotes"]),
                horizontal_asymptotes=sp.FiniteSet(*info["horizontal_asymptotes"]),
                oblique_asymptotes=sp.FiniteSet(*(line.subs(var, given_var) for line in info["oblique_asymptotes"])))
    return {
        "symbolic": str(expr),
        "final_latex": final,
        "steps": steps,
        "answer": info,
        "show_graph": True,
        "graph": graph,
    }
