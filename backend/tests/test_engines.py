import pytest
import sympy as sp

from engines.math import algebra, calculus, linear_algebra, ode, series
from engines.math.common import parse_math
from engines.physics import physics_engine
from pipeline import solve_latex_expression


def final(latex: str) -> str:
    return solve_latex_expression(latex)["final_result_latex"]


# ── Parsing ──────────────────────────────────────────────────────────────────

def test_constants_are_not_symbols():
    assert parse_math(r"\pi") == sp.pi
    assert parse_math(r"e^{x}") == sp.exp(sp.Symbol("x"))


# ── Integrals ────────────────────────────────────────────────────────────────

def test_calculus_integral():
    result = calculus.solve_integral(r"\int_{0}^{\pi} \sin(x) dx")
    assert result["final_latex"] == "2"
    assert result["steps"]


@pytest.mark.parametrize("latex,expected", [
    (r"\int x^3 + 2x\,dx", r"\frac{x^{4}}{4} + x^{2} + C"),
    (r"\int x e^{x} dx", r"\left(x - 1\right) e^{x} + C"),
    (r"\int 2x \cos(x^2) dx", r"\sin{\left(x^{2} \right)} + C"),
    (r"\int_{0}^{\infty} e^{-x} dx", "1"),
    (r"\int_{1}^{2} \frac{1}{x} dx", r"\ln{\left(2 \right)} \approx 0.693147"),
])
def test_integrals(latex, expected):
    assert final(latex) == expected


def test_integral_techniques_are_explained():
    steps = " ".join(calculus.solve_integral(r"\int x e^{x} dx")["steps"])
    assert "partes" in steps
    steps = " ".join(calculus.solve_integral(r"\int 2x \cos(x^2) dx")["steps"])
    assert "sustitución" in steps
    steps = " ".join(calculus.solve_integral(r"\int \frac{x^5 + x^4 - 8}{x^3 - 4x} dx")["steps"])
    assert "División de polinomios" in steps and "fracciones parciales" in steps


def test_definite_integral_has_shaded_area():
    graph = solve_latex_expression(r"\int_{0}^{\pi} \sin(x)\,dx")["graph_data"]
    assert graph and any(t.get("fill") == "toself" for t in graph["data"])


# ── Derivatives and limits ───────────────────────────────────────────────────

@pytest.mark.parametrize("latex,expected", [
    (r"\frac{d}{dx}(x^3 - 4x + 1)", "3 x^{2} - 4"),
    (r"\frac{d^2}{dx^2}(x^3)", "6 x"),
    (r"f'(x) = \ln(x^2+1)", r"\frac{2 x}{x^{2} + 1}"),
])
def test_derivatives(latex, expected):
    assert final(latex) == expected


def test_derivative_graphs_function_and_derivative():
    graph = solve_latex_expression(r"\frac{d}{dx}(x^2)")["graph_data"]
    assert len(graph["data"]) == 2


def test_function_analysis_draws_its_asymptotes():
    graph = solve_latex_expression(r"f(x) = \frac{x^2}{x-1}")["graph_data"]
    names = [trace["name"] for trace in graph["data"]]
    assert "asíntota x = 1" in names and "asíntota y = x + 1" in names


def test_function_analysis_covers_every_section():
    steps = " ".join(algebra.analyze(r"\frac{x^2}{x-1}")["steps"])
    for section in ("Dominio", "Paridad", "Raíces", "Continuidad", "Asíntotas", "Crecimiento",
                    "Concavidad", "Positividad", "Imagen"):
        assert section in steps


def test_product_rule_is_named():
    steps = " ".join(calculus.solve_derivative(r"\frac{d}{dx}(x^2 \sin(x))")["steps"])
    assert "producto" in steps


@pytest.mark.parametrize("latex,expected", [
    (r"\lim_{x \to 0} \frac{\sin(x)}{x}", "1"),
    (r"\lim_{x \to \infty} (1+\frac{1}{x})^x", "e"),
    (r"\lim_{x \to 2} \frac{x^2-4}{x-2}", "4"),
    (r"\lim_{x \to 0} \frac{1}{x}", r"\text{No existe}"),
])
def test_limits(latex, expected):
    assert final(latex) == expected


# ── Algebra ──────────────────────────────────────────────────────────────────

def test_algebra_equation():
    result = algebra.solve_equation("x^2 - 4 = 0")
    assert result["final_latex"] == r"x \in \left\{-2,\; 2\right\}"
    assert "steps" in result


@pytest.mark.parametrize("latex,expected", [
    ("2 + 2", "4"),
    (r"\frac{3}{4} + \frac{1}{8}", r"\frac{7}{8}"),
    ("x^2 - 5x + 6 = 0", r"x \in \left\{2,\; 3\right\}"),
    ("x^3 - 6x^2 + 11x - 6 = 0", r"x \in \left\{1,\; 2,\; 3\right\}"),
    ("2x + 1 \\leq 7", r"x \in \left(-\infty, 3\right]"),
    ("2x + 3y = 6; x - y = 1", r"x = \frac{9}{5},\; y = \frac{4}{5}"),
])
def test_algebra(latex, expected):
    assert final(latex) == expected


def test_complex_roots_are_not_reported_as_real():
    res = algebra.solve_equation("x^2 + 1 = 0")
    assert r"\mathbb{C}" in res["final_latex"]
    assert any("no tiene soluciones reales" in s for s in res["steps"])


def test_trig_equation_general_solution():
    steps = " ".join(algebra.solve_equation(r"\sin(x) = \frac{1}{2}")["steps"])
    assert "solución general" in steps


def test_incompatible_system():
    assert final("x + y = 1; x + y = 2") == r"\text{Sistema incompatible}"


def test_function_analysis_finds_extrema():
    res = algebra.solve_equation("f(x) = x^3 - 3x")
    text = " ".join(res["steps"])
    assert "máximo relativo" in text and "mínimo relativo" in text
    assert res["graph"] is not None


# ── Series ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("latex,expected", [
    (r"\sum_{n=1}^{\infty} \frac{1}{n^2}", r"\frac{\pi^{2}}{6} \approx 1.64493"),
    (r"\sum_{n=1}^{\infty} \frac{1}{n}", r"\text{Diverge}"),
    (r"\sum_{n=0}^{\infty} \frac{1}{2^n}", "2"),
    (r"\sum_{k=1}^{10} k", "55"),
])
def test_series(latex, expected):
    assert series.solve_series(latex)["final_latex"] == expected


# ── Differential equations ───────────────────────────────────────────────────

@pytest.mark.parametrize("latex,expected", [
    ("y' = 2y", r"y{\left(x \right)} = C_{1} e^{2 x}"),
    ("y' = 2y, y(0) = 1", r"y{\left(x \right)} = e^{2 x}"),
    (r"\frac{dy}{dx} = x y", r"y{\left(x \right)} = C_{1} e^{\frac{x^{2}}{2}}"),
])
def test_ode(latex, expected):
    assert ode.solve_ode(latex)["final_latex"] == expected


def test_second_order_ode_uses_characteristic_equation():
    res = ode.solve_ode("y'' + y = 0")
    assert "C_{1}" in res["final_latex"] and "C_{2}" in res["final_latex"]
    assert any("característica" in s for s in res["steps"])


# ── Linear algebra ───────────────────────────────────────────────────────────

M = r"\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}"


def test_determinant():
    assert linear_algebra.solve_linear_algebra(r"\det" + M)["final_latex"] == "-2"


def test_matrix_inverse():
    res = linear_algebra.solve_linear_algebra(M + "^{-1}")
    assert res["final_latex"] == sp.latex(sp.Matrix([[1, 2], [3, 4]]).inv())


def test_matrix_product():
    res = linear_algebra.solve_linear_algebra(M + r" \cdot \begin{pmatrix} 0 & 1 \\ 1 & 0 \end{pmatrix}")
    assert res["final_latex"] == sp.latex(sp.Matrix([[2, 1], [4, 3]]))


def test_matrix_analysis():
    res = linear_algebra.solve_linear_algebra(r"\begin{pmatrix} 2 & 1 \\ 1 & 2 \end{pmatrix}")
    assert r"\det(A) = 3" in res["final_latex"]
    assert "diagonalizable" in " ".join(res["steps"])


def test_incompatible_dimensions_fail_gracefully():
    res = linear_algebra.solve_linear_algebra(M + r"\begin{pmatrix} 1 & 2 & 3 \end{pmatrix}")
    assert res.get("ok") is False


# ── Physics ──────────────────────────────────────────────────────────────────

def test_physics_newton():
    res = physics_engine.solve_physics("F = m a, m = 10, a = 5")
    assert res["final_latex"] == "F = 50"
    assert "Newton" in res["steps"][0]


def test_physics_solves_for_any_unknown():
    res = physics_engine.solve_physics(r"v = v_0 + a t, v = 14, v_0 = 2, a = 3")
    assert res["final_latex"] == "t = 4"


def test_physics_missing_data():
    assert physics_engine.solve_physics("F = m a, m = 10")["final_latex"] == r"\text{Faltan datos}"


# ── Robustness ───────────────────────────────────────────────────────────────

def test_garbage_input_does_not_raise():
    res = solve_latex_expression(r"\frac{{")
    assert res["solved"] is False


# ── Solver failures are reported, never disguised as "no solution" ──────────

def _raise(*args, **kwargs):
    raise NotImplementedError("simulated SymPy failure")


def test_solver_failure_is_not_reported_as_no_solution(monkeypatch):
    monkeypatch.setattr(algebra.sp, "solve", _raise)
    monkeypatch.setattr(algebra.sp, "nsolve", _raise)
    res = algebra.solve_equation("x^2 = 4")
    assert res["ok"] is False
    assert res["final_latex"] == r"\text{No se pudo resolver}"


def test_numeric_fallback_is_flagged_as_partial(monkeypatch):
    monkeypatch.setattr(algebra.sp, "solve", _raise)
    res = algebra.solve_equation("x^2 = 4")
    assert res.get("ok", True)
    assert any("Puede haber otras" in s for s in res["steps"])


def test_genuinely_impossible_equation_says_no_solution():
    assert algebra.solve_equation("x + 1 = x")["final_latex"] == r"\text{Sin solución}"


def test_physics_solver_failure_is_reported(monkeypatch):
    monkeypatch.setattr(physics_engine.sp, "solve", _raise)
    res = physics_engine.solve_physics("F = m a, m = 10, a = 5")
    assert res["ok"] is False


def test_requested_statistic_is_the_one_shown():
    # "mediana" also starts with "media": the final answer must be the median, not the mean
    from pipeline import run_solver
    _, res = run_solver("mediana de 3, 1, 4, 1, 5")
    assert res["final_latex"] == r"\tilde{x} = 3"


def test_misread_latex_is_rejected_not_solved():
    # A word-like symbol means the LaTeX was misread: never solve (and "verify") it
    from engines.math.common import parse_math
    assert parse_math(r"\mathbb{Q} x") is None or not any(
        s.name.isalpha() and len(s.name) > 1 for s in parse_math(r"\mathbb{Q} x").free_symbols)
