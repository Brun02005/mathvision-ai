"""
Vectors in R^n written as tuples: (1, 2, 3) or \\langle 1, 2, 3 \\rangle.
Operations: u + v, u - v, k·u, dot product u \\cdot v, cross product u \\times v,
norm |u| / \\|u\\|, and the analysis of a single vector (norm and unit vector).
"""
import re

import sympy as sp

from engines.math.common import clean_latex, error_result, parse_math

TUPLE = re.compile(r"(?:\\langle|\()\s*([^()]*?,[^()]*?)\s*(?:\\rangle|\))")
_NORM = re.compile(r"^(?:\\\||\\lVert|\||\\vert)\s*V0\s*(?:\\\||\\rVert|\||\\vert)$")
_BINARY = re.compile(r"^V0\s*(\\times|\\cdot|\+|-)\s*V1$")
_SCALAR = re.compile(r"^(.+?)\s*(?:\\cdot)?\s*V0$")


def _tuple_latex(v) -> str:
    return r"\left(" + ",\\; ".join(sp.latex(c) for c in v) + r"\right)"


def _result(symbolic, answer, final, steps):
    return {"symbolic": symbolic, "final_latex": final, "steps": steps, "answer": answer,
            "verified": None, "show_graph": False}


def solve_vectors(latex_expr: str) -> dict:
    s = clean_latex(latex_expr)
    vectors = []

    def repl(m):
        comps = [parse_math(c) for c in m.group(1).split(",")]
        if any(c is None for c in comps):
            raise ValueError
        vectors.append(sp.ImmutableMatrix(comps))
        return f" V{len(vectors) - 1} "

    try:
        expr_s = re.sub(r"\s+", " ", TUPLE.sub(repl, s)).strip()
    except ValueError:
        return error_result(latex_expr, "Componente inválida en un vector.")
    if not vectors:
        return error_result(latex_expr, r"Ejemplo: `(1, 2, 3) \times (4, 5, 6)`")
    names = {f"V{i}": "uvw"[i] if i < 3 else f"v_{i}" for i in range(len(vectors))}
    defs = ",\\quad ".join(f"\\vec{{{names[f'V{i}']}}} = {_tuple_latex(v)}" for i, v in enumerate(vectors))
    steps = [f"Tenemos $${defs}$$"]

    if expr_s == "V0" or _NORM.match(expr_s):
        u = vectors[0]
        norm = sp.sqrt(sum(c**2 for c in u))
        squares = " + ".join(f"({sp.latex(c)})^2" if c.is_negative else f"{sp.latex(c)}^2" for c in u)
        steps.append(f"**Módulo (norma):** $$|\\vec{{u}}| = \\sqrt{{{squares}}} = {sp.latex(sp.simplify(norm))}$$")
        if norm != 0:
            unit = (u / norm).applyfunc(sp.simplify)
            steps.append(f"**Versor** (vector unitario en la misma dirección): $$\\hat{{u}} = \\frac{{\\vec{{u}}}}{{|\\vec{{u}}|}} = {_tuple_latex(unit)}$$")
        return _result(str(list(u)), sp.simplify(norm), f"|\\vec{{u}}| = {sp.latex(sp.simplify(norm))}", steps)

    m = _BINARY.match(expr_s)
    if m and len(vectors) == 2:
        u, v = vectors
        op = m.group(1)
        if u.shape != v.shape:
            return error_result(latex_expr, "Los vectores tienen distinta dimensión.")
        if op == r"\cdot":
            terms = " + ".join(f"({sp.latex(a)})({sp.latex(b)})" for a, b in zip(u, v, strict=True))
            dot = u.dot(v)
            steps.append(f"**Producto escalar:** se multiplican componente a componente y se suman: $$\\vec{{u}} \\cdot \\vec{{v}} = {terms} = {sp.latex(dot)}$$")
            if dot == 0:
                steps.append("Como el producto escalar es $0$, los vectores son **perpendiculares**.")
            else:
                cos = sp.simplify(dot / (sp.sqrt(u.dot(u)) * sp.sqrt(v.dot(v))))
                steps.append(f"Ángulo entre ellos: $\\cos\\theta = \\frac{{\\vec{{u}}\\cdot\\vec{{v}}}}{{|\\vec{{u}}|\\,|\\vec{{v}}|}} = {sp.latex(cos)}$, "
                             f"$\\theta \\approx {sp.latex(sp.N(sp.acos(cos) * 180 / sp.pi, 5))}^\\circ$")
            return _result(expr_s, dot, f"\\vec{{u}} \\cdot \\vec{{v}} = {sp.latex(dot)}", steps)
        if op == r"\times":
            if u.shape[0] != 3:
                return error_result(latex_expr, "El producto vectorial está definido para vectores de 3 componentes.")
            cross = u.cross(v)
            det = (r"\begin{vmatrix} \hat{i} & \hat{j} & \hat{k} \\ "
                   + " & ".join(sp.latex(c) for c in u) + r" \\ " + " & ".join(sp.latex(c) for c in v) + r" \end{vmatrix}")
            steps.append(f"**Producto vectorial:** desarrollamos el determinante $${det} = {_tuple_latex(cross)}$$")
            steps.append("El resultado es perpendicular a ambos vectores "
                         f"(✓ $\\vec{{w}}\\cdot\\vec{{u}} = {sp.latex(cross.dot(u))}$, $\\vec{{w}}\\cdot\\vec{{v}} = {sp.latex(cross.dot(v))}$).")
            return _result(expr_s, cross, f"\\vec{{u}} \\times \\vec{{v}} = {_tuple_latex(cross)}", steps)
        result = u + v if op == "+" else u - v
        steps.append(f"Operamos **componente a componente**: $$\\vec{{u}} {op} \\vec{{v}} = {_tuple_latex(result)}$$")
        return _result(expr_s, result, _tuple_latex(result), steps)

    m = _SCALAR.match(expr_s)
    if m and len(vectors) == 1:
        k = parse_math(m.group(1))
        if k is not None and k.is_number:
            result = k * vectors[0]
            steps.append(f"Multiplicamos cada componente por ${sp.latex(k)}$: $${_tuple_latex(result)}$$")
            return _result(expr_s, result, _tuple_latex(result), steps)

    return error_result(latex_expr, r"Operaciones con vectores: `u + v`, `u - v`, `k u`, `u \cdot v`, `u \times v`, `|u|`.")
