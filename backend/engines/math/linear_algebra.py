"""
Linear algebra: matrix analysis (determinant, rank, inverse, eigenvalues,
reduced row echelon form) and matrix expressions (A + B, A·B, A^{-1}, A^T, \\det A, k·A).
"""
import re
import logging

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

from engines.math.common import clean_latex, parse_math, error_result

logger = logging.getLogger(__name__)

_MATRIX_ENV = re.compile(r"\\begin\{([pbBvV]?matrix|array)\}(?:\{[^}]*\})?(.*?)\\end\{\1\}", re.S)


def _parse_matrix_body(body: str) -> sp.ImmutableMatrix:
    rows = [r for r in re.split(r"\\\\", body) if r.strip()]
    data = []
    for r in rows:
        cells = [parse_math(c) for c in r.split("&")]
        if any(c is None for c in cells):
            raise ValueError(f"Celda inválida en la fila: {r!r}")
        data.append(cells)
    if len({len(r) for r in data}) != 1:
        raise ValueError("Las filas de la matriz tienen distinta cantidad de columnas.")
    return sp.ImmutableMatrix(data)


def _extract(latex_expr: str):
    """Replace every matrix environment with a placeholder. Returns (expression string, {name: Matrix})."""
    matrices = {}

    def repl(m):
        name = f"M{len(matrices)}"
        matrices[name] = _parse_matrix_body(m.group(2))
        return f" det({name}) " if m.group(1) in ("vmatrix", "Vmatrix") else f" {name} "

    s = _MATRIX_ENV.sub(repl, latex_expr)
    return s, matrices


def _to_python(s: str) -> str:
    s = re.sub(r"\\det\s*", "det", s)
    s = re.sub(r"det\s*(M\d+)", r"det(\1)", s)
    s = re.sub(r"\\operatorname\{(rank|rg|tr)\}", r"\1", s)
    s = re.sub(r"\^\{?\s*-1\s*\}?", "**(-1)", s)
    s = re.sub(r"\^\{?\s*(T|t|\\top)\s*\}?", ".T", s)
    s = s.replace(r"\cdot", "*").replace(r"\times", "*").replace("{", "(").replace("}", ")")
    s = re.sub(r"\\frac\((.+?)\)\((.+?)\)", r"((\1)/(\2))", s)
    s = s.replace("\\", "")
    # Implicit product between matrices / scalars: "M0 M1", "2 M0", ") M1"
    s = re.sub(r"(M\d+|\)|\d)\s+(?=(M\d+|\(|det))", r"\1*", s)
    return s.strip()


def _matrix_steps(A: sp.ImmutableMatrix, name: str = "A") -> tuple[list, str]:
    steps = [f"Tenemos la matriz $${name} = {sp.latex(A)}$$ de dimensión ${A.rows} \\times {A.cols}$."]
    summary = []

    rank = A.rank()
    rref, pivots = A.rref()
    steps.append(f"**Forma escalonada reducida** (Gauss-Jordan): $${sp.latex(rref)}$$")
    steps.append(f"**Rango:** $\\operatorname{{rg}}({name}) = {rank}$ (cantidad de pivotes).")
    summary.append(f"\\operatorname{{rg}}({name}) = {rank}")

    if A.is_square:
        det = sp.simplify(A.det())
        if A.rows == 2:
            a, b, c, d = A
            steps.append(f"**Determinante** ($2\\times2$: $ad - bc$): $$\\det({name}) = ({sp.latex(a)})({sp.latex(d)}) - ({sp.latex(b)})({sp.latex(c)}) = {sp.latex(det)}$$")
        elif A.rows == 3:
            steps.append(f"**Determinante** (regla de Sarrus / desarrollo por cofactores): $$\\det({name}) = {sp.latex(det)}$$")
        else:
            steps.append(f"**Determinante** (desarrollo por cofactores): $$\\det({name}) = {sp.latex(det)}$$")
        summary.append(f"\\det({name}) = {sp.latex(det)}")

        if det != 0:
            inv = sp.simplify(A.inv())
            steps.append(f"Como $\\det({name}) \\neq 0$, la matriz es **invertible**: $${name}^{{-1}} = \\frac{{1}}{{\\det {name}}}\\operatorname{{adj}}({name}) = {sp.latex(inv)}$$")
            summary.append(f"{name}^{{-1}} = {sp.latex(inv)}")
        else:
            steps.append(f"Como $\\det({name}) = 0$, la matriz es **singular** (no invertible).")

        if A.rows <= 4:
            lam = sp.Symbol("lambda")
            char = sp.factor(A.charpoly(lam).as_expr())
            steps.append(f"**Polinomio característico:** $$p(\\lambda) = \\det({name} - \\lambda I) = {sp.latex(char)}$$")
            try:
                eig = A.eigenvects()
                for val, mult, vecs in eig:
                    vecs_l = ",\\; ".join(sp.latex(sp.simplify(v)) for v in vecs)
                    steps.append(f"Autovalor $\\lambda = {sp.latex(val)}$ (multiplicidad {mult}) con autovector(es): $${vecs_l}$$")
                vals_l = ",\\; ".join(sp.latex(v) for v, _, _ in eig)
                summary.append(f"\\lambda \\in \\left\\{{{vals_l}\\right\\}}")
                if A.is_diagonalizable():
                    steps.append(f"Hay una base de autovectores: ${name}$ es **diagonalizable**.")
            except Exception as e:
                logger.warning(f"eigenvects failed: {e}")

    final = r"\begin{array}{l} " + r" \\ ".join(summary) + r" \end{array}"
    return steps, final


def solve_linear_algebra(latex_expr: str) -> dict:
    s = clean_latex(latex_expr)
    try:
        expr_s, matrices = _extract(s)
    except ValueError as e:
        return error_result(latex_expr, str(e))
    if not matrices:
        return error_result(latex_expr, r"Ejemplo: `\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}`")

    py = _to_python(expr_s)

    if re.fullmatch(r"M0", py):
        steps, final = _matrix_steps(matrices["M0"])
        return {"symbolic": str(matrices["M0"]), "final_latex": final, "steps": steps, "show_graph": False}

    local = dict(matrices)
    local.update({
        "det": lambda m: sp.simplify(m.det()),
        "rank": lambda m: m.rank(),
        "rg": lambda m: m.rank(),
        "tr": lambda m: m.trace(),
    })
    try:
        result = parse_expr(py, local_dict=local, transformations=standard_transformations)
        if isinstance(result, sp.MatrixBase):
            result = sp.simplify(result)
    except Exception as e:
        logger.warning(f"matrix expression failed: {py!r}: {e}")
        msg = str(e)
        hint = None
        if "shape" in msg.lower() or "dimension" in msg.lower():
            hint = "Las dimensiones de las matrices no son compatibles para esta operación."
        elif "invertible" in msg.lower() or "det" in msg.lower():
            hint = "La matriz no es invertible (determinante nulo)."
        return error_result(latex_expr, hint)

    names = {k: chr(ord("A") + i) for i, k in enumerate(matrices)}
    steps = ["Definimos las matrices: $$" + ",\\quad ".join(f"{names[k]} = {sp.latex(m)}" for k, m in matrices.items()) + "$$"]
    pretty = py
    for k, v in names.items():
        pretty = pretty.replace(k, v)
    if "**(-1)" in py:
        steps.append(r"Para la **inversa** usamos $A^{-1} = \frac{1}{\det A}\operatorname{adj}(A)$ (requiere $\det A \neq 0$).")
    if "det(" in py:
        steps.append("Calculamos el **determinante** (desarrollo por cofactores).")
    if re.search(r"M\d+\s*\*\s*M\d+", py):
        steps.append(r"En el **producto de matrices**, el elemento $(i,j)$ es la fila $i$ de la primera por la columna $j$ de la segunda: $c_{ij} = \sum_k a_{ik} b_{kj}$.")
    if ".T" in py:
        steps.append("La **transpuesta** intercambia filas por columnas.")
    steps.append(f"**Resultado:** $${sp.latex(result)}$$")

    return {"symbolic": pretty, "final_latex": sp.latex(result), "steps": steps, "show_graph": False}
