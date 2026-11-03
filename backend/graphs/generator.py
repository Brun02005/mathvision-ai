"""
Graph data generator for Plotly.js visualization.

Solvers describe *what* to plot through a `graph` spec built from SymPy
expressions they already computed, so nothing is re-parsed from LaTeX:

    {
        "var": x,
        "curves": [{"expr": f, "label": "f(x)"}, {"expr": f_prime, "label": "f'(x)"}],
        "x_range": (-10, 10),                           # optional
        "points": [{"x": 2, "y": 0, "label": "raíz"}],  # optional markers
        "fill": {"a": 0, "b": 3.14},                    # optional shaded area under curves[0]
        "vlines": [{"x": 1, "label": "asíntota x = 1"}], # optional vertical lines (asymptotes)
    }
"""
import logging

import numpy as np
import sympy as sp

logger = logging.getLogger(__name__)

PALETTE = ["#6366f1", "#ec4899", "#10b981", "#f59e0b"]


def _evaluate(expr, var, xs):
    f = sp.lambdify(var, expr, modules=["numpy"])
    with np.errstate(all="ignore"):
        ys = np.asarray(f(xs), dtype=complex) * np.ones_like(xs)
    # Keep only (almost) real values
    ys = np.where(np.abs(ys.imag) < 1e-9, ys.real, np.nan).astype(float)
    return np.where(np.isfinite(ys), ys, np.nan)


def _break_asymptotes(ys, clip):
    """Insert gaps where the curve jumps (vertical asymptotes) instead of drawing a vertical line."""
    ys = np.where(np.abs(ys) > clip, np.nan, ys)
    jumps = np.abs(np.diff(ys)) > clip
    ys[1:][jumps] = np.nan
    return ys


def _safe_float(v):
    try:
        f = float(v)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _to_json_list(ys):
    return [None if np.isnan(v) else round(float(v), 6) for v in ys]


def generate_graph(spec: dict, n_points: int = 600) -> dict | None:
    """Build Plotly `{data, layout}` from a solver graph spec. Returns None if nothing is plottable."""
    if not spec or not spec.get("curves"):
        return None
    var = spec.get("var", sp.Symbol("x"))
    a, b = spec.get("x_range") or (-10, 10)
    a, b = float(a), float(b)
    xs = np.linspace(a, b, n_points)

    traces, all_y = [], []
    for i, curve in enumerate(spec["curves"]):
        expr = sp.sympify(curve["expr"])
        if expr.free_symbols - {var}:
            continue
        try:
            ys = _evaluate(expr, var, xs)
        except Exception as e:
            logger.warning(f"Graph evaluation failed for {expr}: {e}")
            continue
        if np.all(np.isnan(ys)):
            continue
        all_y.append(ys)
        traces.append({
            "x": [round(float(v), 6) for v in xs],
            "y": ys,
            "type": "scatter",
            "mode": "lines",
            "name": curve.get("label", "f(x)"),
            "line": {"color": PALETTE[i % len(PALETTE)], "width": 2.5,
                     "dash": "dash" if i > 0 else "solid"},
        })

    if not traces:
        return None

    finite = np.concatenate([y[np.isfinite(y)] for y in all_y])
    clip = max(float(np.percentile(np.abs(finite), 95)) * 3, 10.0) if finite.size else 50.0
    for t in traces:
        t["y"] = _to_json_list(_break_asymptotes(t["y"], clip))

    fill = spec.get("fill")
    if fill:
        fa, fb = _safe_float(fill.get("a")), _safe_float(fill.get("b"))
        if fa is not None and fb is not None:
            lo, hi = sorted((fa, fb))
            fx = np.linspace(lo, hi, 200)
            try:
                fy = _evaluate(sp.sympify(spec["curves"][0]["expr"]), var, fx)
                traces.insert(0, {
                    "x": [float(v) for v in fx] + [hi, lo],
                    "y": _to_json_list(fy) + [0, 0],
                    "type": "scatter", "mode": "lines", "fill": "toself",
                    "fillcolor": "rgba(99,102,241,0.25)", "line": {"width": 0},
                    "name": "Área", "hoverinfo": "skip",
                })
            except Exception as e:
                logger.warning(f"Area fill failed: {e}")

    shown = [v for t in traces for v in t["y"] if v is not None]
    y_lo, y_hi = (min(shown), max(shown)) if shown else (-clip, clip)
    for line in spec.get("vlines", []):
        vx = _safe_float(line.get("x"))
        if vx is not None and a <= vx <= b:
            traces.append({
                "x": [vx, vx], "y": [y_lo, y_hi], "type": "scatter", "mode": "lines",
                "name": line.get("label", f"x = {vx}"), "line": {"color": "#94a3b8", "width": 1.5, "dash": "dot"},
            })

    markers = []
    for p in spec.get("points", []):
        px, py = _safe_float(p.get("x")), _safe_float(p.get("y"))
        if px is not None and py is not None and a <= px <= b:
            markers.append((px, py, p.get("label", "")))
    if markers:
        traces.append({
            "x": [m[0] for m in markers],
            "y": [m[1] for m in markers],
            "text": [m[2] for m in markers],
            "type": "scatter", "mode": "markers+text", "textposition": "top center",
            "marker": {"size": 9, "color": "#f59e0b"},
            "name": "Puntos clave",
        })

    return {
        "data": traces,
        "layout": {
            "showlegend": len(traces) > 1,
            "xaxis": {"title": {"text": str(var)}, "zeroline": True},
            "yaxis": {"title": {"text": "y"}, "zeroline": True},
        },
    }


def function_spec(expr, var=None, label="f(x)") -> dict | None:
    """Single-curve spec when the expression depends on exactly one variable."""
    free = getattr(expr, "free_symbols", set())
    if len(free) != 1:
        return None
    var = var or next(iter(free))
    return {"var": var, "curves": [{"expr": expr, "label": label}]}
