"""
Graph data generator for Plotly.js visualization.
Only generates graphs when meaningful (show_graph=True from solver).
"""
import numpy as np
import sympy as sp
from sympy.parsing.latex import parse_latex
import logging

logger = logging.getLogger(__name__)


def generate_function_graph_data(latex_expr: str, x_range=(-10, 10), points=400) -> dict | None:
    """
    Generate Plotly-compatible data for a function f(x).
    Returns None if no meaningful graph can be produced.
    """
    x_sym = sp.Symbol('x')

    # Parse the expression
    expr = None
    try:
        expr = parse_latex(latex_expr)
    except Exception:
        pass
    if expr is None:
        try:
            expr = sp.sympify(latex_expr.replace('^', '**'))
        except Exception:
            return None

    # If it's an equation, graph the LHS - RHS
    if isinstance(expr, sp.Eq):
        expr = expr.lhs - expr.rhs

    # Must have x as free symbol
    if x_sym not in expr.free_symbols:
        return None

    # Lambdify for fast numeric evaluation
    try:
        f = sp.lambdify(x_sym, expr, modules=['numpy'])
        x_vals = np.linspace(x_range[0], x_range[1], points)
        y_vals = f(x_vals)

        # Clip extreme values for display
        y_vals = np.where(np.isfinite(y_vals), y_vals, np.nan)
        y_median = np.nanmedian(np.abs(y_vals))
        clip = max(y_median * 10, 50)
        y_vals = np.clip(y_vals, -clip, clip)

        title = f"f(x) = {sp.latex(expr)}"

        return {
            "data": [{
                "x": x_vals.tolist(),
                "y": y_vals.tolist(),
                "type": "scatter",
                "mode": "lines",
                "name": "f(x)",
                "line": {"color": "#6366f1", "width": 2.5},
            }],
            "layout": {
                "title": {"text": title, "font": {"size": 14}},
                "xaxis": {"title": "x", "zeroline": True},
                "yaxis": {"title": "f(x)", "zeroline": True},
            }
        }
    except Exception as e:
        logger.warning(f"Graph generation failed: {e}")
        return None
