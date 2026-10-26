"""
Shared parsing helpers for every solver.

parse_latex() reads constants as plain symbols (\\pi → Symbol('pi'),
e^{x} → Symbol('e')**x), which silently produces wrong results such as
∫_0^π sin(x) dx = 1 - cos(pi). Everything goes through `parse_math` so
constants are fixed in a single place.
"""
import re
import logging

import sympy as sp
from sympy.parsing.latex import parse_latex
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application, convert_xor,
)

logger = logging.getLogger(__name__)

x = sp.Symbol('x')

_CONSTANTS = {
    sp.Symbol('pi'): sp.pi,
    sp.Symbol('e'): sp.E,
}

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)


def clean_latex(latex_expr: str) -> str:
    """Normalize OCR / user LaTeX: delimiters, spacing commands, \\left/\\right."""
    s = latex_expr.strip()
    s = re.sub(r'^\$+|\$+$', '', s)
    s = re.sub(r'^\\\[|\\\]$', '', s)
    s = re.sub(r'^\\\(|\\\)$', '', s)
    s = s.replace(r'\left', '').replace(r'\right', '')
    s = re.sub(r'\\[,;:!]|\\quad|\\qquad', ' ', s)
    s = s.replace(r'\displaystyle', '').replace(r'\dfrac', r'\frac').replace(r'\tfrac', r'\frac')
    # OCR artifacts: empty integral limits
    s = re.sub(r'\\int_\{\s*\}\^\{\s*\}', r'\\int', s)
    s = re.sub(r'\\int_\{\s*\}', r'\\int', s)
    s = re.sub(r'\\int\^\{\s*\}', r'\\int', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def fix_constants(expr):
    """Replace symbols that are really mathematical constants."""
    if expr is None or not hasattr(expr, 'subs'):
        return expr
    try:
        return expr.xreplace(_CONSTANTS)
    except Exception:
        return expr


def _sympify_fallback(s: str):
    plain = (s.replace(r'\cdot', '*').replace(r'\times', '*').replace(r'\div', '/')
              .replace('{', '(').replace('}', ')').replace('\\', ''))
    return parse_expr(plain, transformations=_TRANSFORMS, local_dict={'e': sp.E, 'pi': sp.pi})


def parse_math(latex_str: str):
    """Parse LaTeX (or plain math like `x**2 + 1`) into a SymPy object. Returns None on failure."""
    if latex_str is None or not latex_str.strip():
        return None
    s = clean_latex(latex_str)
    try:
        return fix_constants(parse_latex(s))
    except Exception as e:
        logger.debug(f"parse_latex failed for {s!r}: {e}")
    try:
        return fix_constants(_sympify_fallback(s))
    except Exception as e:
        logger.debug(f"sympify fallback failed for {s!r}: {e}")
    return None


def split_top_level(s: str, seps=(',', ';')) -> list[str]:
    """Split on separators that are not inside braces/parentheses/brackets."""
    parts, depth, buf = [], 0, []
    for ch in s:
        if ch in '({[':
            depth += 1
        elif ch in ')}]':
            depth -= 1
        if ch in seps and depth == 0:
            parts.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append(''.join(buf))
    return [p.strip() for p in parts if p.strip()]


def pick_variable(expr, preferred=x):
    """Choose the variable to work with: x if present, otherwise the first symbol alphabetically."""
    free = sorted(getattr(expr, 'free_symbols', set()), key=lambda s: s.name)
    if preferred in free:
        return preferred
    return free[0] if free else preferred


def latex(expr) -> str:
    return sp.latex(expr)


def error_result(latex_expr: str, hint: str = None) -> dict:
    steps = [
        "No se pudo interpretar la expresión matemática.",
        "Verificá que esté correctamente escrita en LaTeX.",
        f"Expresión recibida: `{latex_expr}`",
    ]
    if hint:
        steps.append(hint)
    return {
        "symbolic": latex_expr,
        "final_latex": r"\text{No se pudo interpretar la expresión}",
        "steps": steps,
        "show_graph": False,
        "ok": False,
    }
