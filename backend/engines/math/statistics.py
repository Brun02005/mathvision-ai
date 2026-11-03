"""
Descriptive statistics of a list of numbers: mean, median, mode, range,
variance and standard deviation (population and sample).

Separators: commas, or semicolons when the numbers use a decimal comma
(2,5; 3,1; 4). Exact arithmetic: 1/3 stays 1/3, decimals are shown at the end.
"""
import re
from collections import Counter

import sympy as sp

from engines.math.common import clean_latex, error_result, parse_math

SEP = r",\; "
LABELS = {
    "mean": r"\bar{x}", "median": r"\tilde{x}", "mode": r"\text{Mo}",
    "variance": r"\sigma^2", "std": r"\sigma",
}


def _parse_values(latex_expr: str):
    s = clean_latex(latex_expr)
    s = re.sub(r"\\[{}]|[{}\[\]]|\\left|\\right", " ", s).strip()
    if ";" in s:
        parts = [p.replace(",", ".") for p in s.split(";")]
    else:
        parts = s.split(",")
    values = []
    for p in (p.strip() for p in parts):
        if not p:
            continue
        v = parse_math(p)
        if v is None or not v.is_number or not v.is_real:
            return None
        values.append(sp.nsimplify(v, rational=True) if v.has(sp.Float) else v)
    return values


def _approx(v) -> str:
    return sp.latex(v) if v.is_Rational and v.q == 1 else f"{sp.latex(v)} \\approx {sp.latex(sp.N(v, 6))}"


def solve_statistics(latex_expr: str, stat: str | None = None) -> dict:
    values = _parse_values(latex_expr)
    if not values or len(values) < 2:
        return error_result(latex_expr, "Escribí al menos dos números separados por comas, p. ej. `media de 2, 4, 4, 5, 7`.")

    data = sorted(values)
    n = len(data)
    total = sum(data)
    mean = sp.Rational(total, n) if total.is_Rational else total / n
    mid = n // 2
    median = data[mid] if n % 2 else (data[mid - 1] + data[mid]) / 2
    counts = Counter(data)
    top = max(counts.values())
    modes = sorted(v for v, c in counts.items() if c == top) if top > 1 else []
    squares = [(v - mean) ** 2 for v in data]
    variance = sp.nsimplify(sum(squares) / n)
    sample_variance = sp.nsimplify(sum(squares) / (n - 1))
    std, sample_std = sp.sqrt(variance), sp.sqrt(sample_variance)

    data_l = SEP.join(sp.latex(v) for v in data)
    steps = [
        f"Ordenamos los ${n}$ datos: $${data_l}$$",
        f"**Media:** $$\\bar{{x}} = \\frac{{\\sum x_i}}{{n}} = \\frac{{{sp.latex(total)}}}{{{n}}} = {_approx(mean)}$$",
        (f"**Mediana:** con $n = {n}$ impar, es el dato central (posición ${mid + 1}$): $\\tilde{{x}} = {sp.latex(median)}$"
         if n % 2 else
         f"**Mediana:** con $n = {n}$ par, promediamos los dos datos centrales: "
         f"$\\tilde{{x}} = \\frac{{{sp.latex(data[mid - 1])} + {sp.latex(data[mid])}}}{{2}} = {_approx(median)}$"),
        (f"**Moda:** el valor más repetido ({top} veces): $\\text{{Mo}} = {SEP.join(sp.latex(m) for m in modes)}$"
         if modes else "**Moda:** ningún valor se repite, la distribución **no tiene moda**."),
        f"**Rango:** ${sp.latex(data[-1])} - {sp.latex(data[0])} = {sp.latex(data[-1] - data[0])}$",
        f"**Varianza poblacional:** $$\\sigma^2 = \\frac{{\\sum (x_i - \\bar{{x}})^2}}{{n}} = \\frac{{{sp.latex(sum(squares))}}}{{{n}}} = {_approx(variance)}$$",
        f"**Desvío estándar poblacional:** $\\sigma = \\sqrt{{\\sigma^2}} = {_approx(std)}$",
        f"**Varianza muestral** (dividimos por $n - 1$): $s^2 = {_approx(sample_variance)}$, desvío muestral $s = {_approx(sample_std)}$",
    ]

    answer = {
        "n": sp.Integer(n), "mean": mean, "median": median,
        "mode": sp.FiniteSet(*modes), "range": data[-1] - data[0],
        "variance": variance, "std": std,
        "sample_variance": sample_variance, "sample_std": sample_std,
    }
    if stat in LABELS:
        value = answer[stat]
        final = (f"{LABELS[stat]} = " + (SEP.join(sp.latex(m) for m in modes) if modes else r"\text{no hay moda}")
                 if stat == "mode" else f"{LABELS[stat]} = {_approx(value)}")
    else:
        final = (r"\begin{array}{l} " + rf"\bar{{x}} = {_approx(mean)} \\ \tilde{{x}} = {_approx(median)} \\ "
                 rf"\sigma = {_approx(std)} \end{{array}}")

    return {"symbolic": str(data), "final_latex": final, "steps": steps, "answer": answer,
            "verified": None, "show_graph": False}
