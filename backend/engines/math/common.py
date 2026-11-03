"""
Shared parsing helpers for every solver.

parse_latex() has several traps that silently produce wrong results, so
everything goes through `parse_math`, which fixes them in a single place:
- constants come back as plain symbols (\\pi → Symbol('pi'), e^{x} → Symbol('e')**x),
  giving things like ∫_0^π sin(x) dx = 1 - cos(pi);
- `i` is a symbol, so (2+3i)(1-i) is not computed as a complex number;
- \\log_{b}(x) is an unevaluated two-argument log that solve() cannot handle,
  so log equations come back as "no solution";
- \\log and \\ln are both read as the natural log;
- free text is accepted as a product of one-letter symbols ("hola" = h·o·l·a).

Conventions: \\log without a base is the decimal logarithm (as in school and
in Argentine universities); \\ln is the natural logarithm.
"""
import re
import logging

import sympy as sp
from sympy.parsing.latex import parse_latex
from sympy.printing.latex import LatexPrinter
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application, convert_xor,
)

logger = logging.getLogger(__name__)

# Show the natural log as \ln everywhere: with our convention \log means base 10,
# so SymPy's default "\log(x)" for ln(x) would be read as a decimal logarithm.
LatexPrinter._default_settings["ln_notation"] = True
# arctan/arcsin/arccos, as written in Argentine courses (SymPy's default is \operatorname{atan})
LatexPrinter._default_settings["inv_trig_style"] = "full"

x = sp.Symbol('x')

_CONSTANTS = {
    sp.Symbol('pi'): sp.pi,
    sp.Symbol('e'): sp.E,
}

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)


_UNICODE = {
    "²": "^{2}", "³": "^{3}", "·": r" \cdot ", "×": r" \times ", "−": "-", "÷": "/",
    "π": r"\pi ", "∞": r"\infty ", "≤": r" \leq ", "≥": r" \geq ", "°": r"^{\circ}",
}
# Spanish (and alternative) names → the LaTeX command SymPy knows
_FUNCTION_ALIASES = {
    "sen": "sin", "tg": "tan", "cotg": "cot", "ctg": "cot", "cosec": "csc", "arcsen": "arcsin",
    "arctg": "arctan", "senh": "sinh", "sin": "sin", "cos": "cos", "tan": "tan", "cot": "cot",
    "sec": "sec", "csc": "csc", "arcsin": "arcsin", "arccos": "arccos", "arctan": "arctan",
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh", "ln": "ln", "log": "log", "exp": "exp",
}
_ALIAS_RE = "|".join(sorted(_FUNCTION_ALIASES, key=len, reverse=True))
_FUNCS = r"arcsin|arccos|arctan|sinh|cosh|tanh|sin|cos|tan|cot|sec|csc|ln|log|exp"
# Argument written without parentheses: x, 2x, 30, \pi, 2\pi, \theta, \frac{a}{b}, optionally with a power (x^2)
_BARE_ARG = (r"(?:\\frac\{[^{}]*\}\{[^{}]*\}"
             r"|(?:\d+(?:\.\d+)?\s*)?(?:\\(?:pi|theta|alpha|beta|phi|varphi)(?![a-zA-Z])|[a-zA-Z](?![a-zA-Z]))"
             r"|\d+(?:\.\d+)?)(?:\^\{[^{}]*\}|\^\w)?")
_FUNC_WITHOUT_PARENS = re.compile(
    rf"\\({_FUNCS})(?![a-zA-Z])((?:\^\{{[^{{}}]*\}}|\^\w)?)((?:_\{{[^{{}}]*\}})?)\s*(?![\s(\{{])({_BARE_ARG})")


def clean_latex(latex_expr: str) -> str:
    """Normalize OCR / user LaTeX into the subset parse_latex reads correctly."""
    s = latex_expr.strip()
    for k, v in _UNICODE.items():
        s = s.replace(k, v)
    s = re.sub(r'^\$+|\$+$', '', s)
    s = re.sub(r'^\\\[|\\\]$', '', s)
    s = re.sub(r'^\\\(|\\\)$', '', s)
    # Macros of the visual editor (MathLive) → standard LaTeX
    s = (s.replace(r'\exponentialE', 'e').replace(r'\imaginaryI', 'i').replace(r'\differentialD', 'd')
          .replace(r'\mleft', r'\left').replace(r'\mright', r'\right'))
    s = s.replace(r'\left', '').replace(r'\right', '')
    if r'\int' in s:
        s = re.sub(r'(?<![a-zA-Z\\])d\s+([a-z])(?![a-zA-Z])', r'd\1', s)  # "d x" → "dx"
    # "pi" typed as letters is π, never p·i (which would even become p times the imaginary unit)
    s = re.sub(r'(?<![a-zA-Z\\])pi(?![a-zA-Z])', r'\\pi ', s)
    s = re.sub(r'\\[,;:!]|\\quad|\\qquad', ' ', s)
    s = s.replace(r'\displaystyle', '').replace(r'\dfrac', r'\frac').replace(r'\tfrac', r'\frac')
    s = re.sub(r'\\(?:no)?limits', '', s)
    # Upright differentials and function names: \mathrm{d}x, \operatorname{sen}(x), \text{tg} x
    s = re.sub(r'\\(?:mathrm|text|textrm|operatorname)\s*\{\s*d\s*\}', 'd', s)
    s = re.sub(rf'\\(?:mathrm|text|textrm|operatorname)\s*\{{\s*({_ALIAS_RE})\s*\}}',
               lambda m: '\\' + _FUNCTION_ALIASES[m.group(1)] + ' ', s)
    # Spanish names written as commands (\sen x, \tg x), whatever precedes them ("x\sen x")
    s = re.sub(rf'\\({_ALIAS_RE})(?![a-zA-Z])', lambda m: '\\' + _FUNCTION_ALIASES[m.group(1)], s)
    # Function names typed without backslash: sen(x), tg x, ln(x). The lookbehind excludes "\"
    # so an existing command is never touched (x\ln x must not become x\\ln x, a LaTeX line break)
    s = re.sub(rf'(?<![a-zA-Z\\])({_ALIAS_RE})(?![a-zA-Z])(?=\s*[(\\{{^0-9a-z])',
               lambda m: '\\' + _FUNCTION_ALIASES[m.group(1)] + ' ', s)
    # Degrees: 30^\circ → 30π/180
    s = re.sub(r'(\d+(?:\.\d+)?)\s*\^\s*\{?\s*\\circ\s*\}?', r'(\\frac{\1 \\pi}{180})', s)
    # OCR artifacts: empty integral limits
    s = re.sub(r'\\int_\{\s*\}\^\{\s*\}', r'\\int', s)
    s = re.sub(r'\\int_\{\s*\}', r'\\int', s)
    s = re.sub(r'\\int\^\{\s*\}', r'\\int', s)
    # One-character log base without braces (\log_2 32 means base 2 of 32), then decimal log when there is no base
    s = re.sub(r'\\log\s*_\s*([0-9a-z])', r'\\log_{\1}', s)
    s = re.sub(r'\\log(?!\s*_)', r'\\log_{10}', s)
    # \sin x \cdot \cos x is sin(x)·cos(x): without explicit parentheses parse_latex would
    # read sin(x·cos x). Wrap a bare argument (x, 2x, 30, \pi, \frac{a}{b}) in parentheses.
    s = re.sub(r'\s+', ' ', s)
    s = _FUNC_WITHOUT_PARENS.sub(lambda m: f"\\{m.group(1)}{m.group(2)}{m.group(3)}({m.group(4)})", s)
    # x(x - 1) is a product, not "function x applied to x - 1" (f, g, h, y, u, v stay functions: f(x), y(0))
    s = re.sub(r'(?<![\\a-zA-Z])([a-eik-twxz])\s*\(', r'\1 \\cdot (', s)
    # Percentages: 15\% → (15/100); "15% de 200" → 15/100 · 200
    s = re.sub(r'(\d+(?:[.,]\d+)?)\s*\\?%', lambda m: f"({m.group(1).replace(',', '.')}/100)", s)
    s = re.sub(r'(/100\))\s*(?:de|of|del)\s+', r'\1 \\cdot ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# Plain words that may legitimately appear in a math expression
_MATH_WORDS = {
    "sqrt", "sinh", "cosh", "tanh", "asin", "acos", "atan", "arcsin", "arccos", "arctan",
    "frac", "cdot", "times", "left", "right", "text", "mathrm", "operatorname", "infty",
    "lambda", "theta", "alpha", "beta", "gamma", "delta", "sigma", "omega", "prime",
}


# Short Spanish words that are never math ("e a la x" must not become e·a·l·a·x)
_STOPWORDS = {"de", "del", "la", "las", "el", "los", "al", "en", "es", "un", "una", "que", "con",
              "si", "se", "su", "lo", "le", "da", "son", "hay", "cual", "como", "para"}


def natural_language_words(s: str) -> list[str]:
    """Words that are not math: a sign the input is a word problem or free text."""
    stripped = re.sub(r'\\(operatorname|mathrm|mathbf|begin|end)\{[^}]*\}', ' ', s)
    stripped = re.sub(r'\\[a-zA-Z]+', ' ', stripped)
    words = re.findall(r'[a-zA-ZáéíóúñÁÉÍÓÚÑ]{4,}', stripped)
    short = [w for w in re.findall(r'(?<![a-zA-Z_^])[a-zA-ZáéíóúñÁÉÍÓÚÑ]{2,4}(?![a-zA-Z])', stripped)
             if w.lower() in _STOPWORDS]
    return [w for w in words if w.lower() not in _MATH_WORDS] + short


def _evaluate_logs(expr):
    """parse_latex builds log(x, b) unevaluated; rebuild it as log(x)/log(b) so solve() understands it."""
    return expr.replace(lambda e: isinstance(e, sp.log) and len(e.args) == 2,
                        lambda e: sp.log(*e.args))


def _real_odd_roots(expr):
    """∛(-27) is -3 in a calculator; SymPy's principal root would be the complex 3·(-1)^(1/3)."""
    return expr.replace(
        lambda e: (e.is_Pow and e.exp.is_Rational and e.exp.q % 2 == 1 and e.exp.q > 1
                   and e.base.is_number and e.base.is_negative),
        lambda e: sp.real_root(e.base, e.exp.q) ** e.exp.p)


def fix_constants(expr, imaginary_unit: bool = True):
    """Replace symbols that are really mathematical constants (π, e and, optionally, i)."""
    if expr is None or not hasattr(expr, 'subs'):
        return expr
    mapping = dict(_CONSTANTS)
    if imaginary_unit:
        mapping[sp.Symbol('i')] = sp.I
    try:
        return _real_odd_roots(_evaluate_logs(expr.xreplace(mapping)))
    except Exception:
        return expr


_GREEK = {
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta", "theta", "vartheta",
    "iota", "kappa", "lambda", "mu", "nu", "xi", "rho", "sigma", "tau", "upsilon", "phi", "varphi",
    "chi", "psi", "omega", "Gamma", "Delta", "Theta", "Lambda", "Xi", "Sigma", "Phi", "Psi", "Omega",
}


# A variable: one letter (optionally with digits), or a Greek letter, with an optional
# subscript (v_0, v_{max}) and primes (y'). Anything else ("mathrm", "_", "log_") is a misread.
# No "x2": typed on a phone it usually means x², not a variable called x2 (indices are x_2)
_VALID_NAME = re.compile(r"^(?:[a-zA-Z]|" + "|".join(sorted(_GREEK, key=len, reverse=True))
                         + r")(?:_\{?[a-zA-Z0-9]+\}?)?'*$")


def _misread(expr) -> bool:
    """
    A symbol that does not look like a variable ("mathrm", "text", "partial", "circ", "_")
    means the LaTeX was misread. Solving it anyway produces a confident wrong answer,
    and verification cannot catch it because it checks the misread expression against itself.
    """
    return any(not _VALID_NAME.match(s.name) for s in getattr(expr, 'free_symbols', ()))


# ── Safe evaluation ───────────────────────────────────────────────────────────
# SymPy's parse_expr runs Python's eval() on the text. User input can only reach it
# through safe_parse_expr, which applies three independent layers:
#   1. a closed alphabet: no "_" (no dunders), quotes, brackets, ":" (no lambda), ";" or "@";
#   2. no attribute access ("x.attr"), except the matrix transpose ".T" when allowed;
#   3. eval runs with NO Python builtins (no open, exec, eval, chr, getattr, __import__),
#      only SymPy's public names.
_SAFE_ALPHABET = re.compile(r"^[A-Za-z0-9\s+\-*/^().,=<>!|]*$")
_ATTRIBUTE = re.compile(r"[A-Za-z0-9_)\]]\s*\.\s*(?=[A-Za-z_])")
# An explicit allowlist, not "all of SymPy": SymPy also exports sympify/S/parse_expr (which
# eval strings with full builtins), lambdify, plotting, printing and test runners.
_SAFE_NAMES = (
    # what parse_expr's own transformations emit
    "Symbol Integer Float Rational Function "
    # constants
    "pi E I oo zoo nan "
    # functions a math exercise uses
    "sin cos tan cot sec csc asin acos atan acot asec acsc atan2 sinh cosh tanh coth asinh acosh atanh "
    "exp log ln sqrt cbrt root Abs sign floor ceiling factorial binomial gamma re im arg conjugate "
    "Min Max Eq Ne Lt Le Gt Ge Matrix ImmutableMatrix"
).split()
_SAFE_GLOBALS = {name: getattr(sp, name) for name in _SAFE_NAMES}
_SAFE_GLOBALS["__builtins__"] = {}


class UnsafeExpression(ValueError):
    """The text contains something that is not plain math: it is never evaluated."""


def safe_parse_expr(text: str, local_dict: dict | None = None, transformations=_TRANSFORMS,
                    allow_transpose: bool = False):
    if len(text) > 4000 or not _SAFE_ALPHABET.match(text):
        raise UnsafeExpression("characters outside the math alphabet")
    checked = re.sub(r"\.\s*T\b", " ", text) if allow_transpose else text
    if _ATTRIBUTE.search(checked):
        raise UnsafeExpression("attribute access")
    return parse_expr(text, local_dict=dict(local_dict or {}), global_dict=dict(_SAFE_GLOBALS),
                      transformations=transformations)


# Names the plain-text fallback understands, as typed by people (arctan, ln, sen...)
_FALLBACK_NAMES = {
    **{name.lower(): getattr(sp, name) for name in _SAFE_NAMES if name[0].islower() and len(name) > 1},
    "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan, "arcsen": sp.asin, "arctg": sp.atan,
    "sen": sp.sin, "tg": sp.tan, "ln": sp.log, "pi": sp.pi, "e": sp.E,
}


def _sympify_fallback(s: str):
    plain = (s.replace(r'\cdot', '*').replace(r'\times', '*').replace(r'\div', '/')
              .replace('{', '(').replace('}', ')').replace('\\', ''))
    # Every multi-letter word must be a known function. Otherwise SymPy splits it into
    # one-letter symbols ("frac" → f·r·a·c) and the result looks like valid math: a
    # confident wrong answer that the misread check cannot catch (all names are one letter).
    for word in re.findall(r"[A-Za-z]{2,}", plain):
        if word.lower() not in _FALLBACK_NAMES:
            raise UnsafeExpression(f"unknown word {word!r}")
    return safe_parse_expr(plain, local_dict={'e': sp.E, 'pi': sp.pi, **_FALLBACK_NAMES})


def parse_math(latex_str: str):
    """Parse LaTeX (or plain math like `x**2 + 1`) into a SymPy object. Returns None on failure."""
    if latex_str is None or not latex_str.strip():
        return None
    s = clean_latex(latex_str)
    if natural_language_words(s):
        return None
    # "x2" (letter followed by a digit) is ambiguous: parse_latex reads x·2, but typed on a
    # phone it usually means x². Refuse instead of guessing; the AI tier can disambiguate.
    if re.search(r'(?<![\\a-zA-Z_^{])[a-zA-Z]\d', s):
        return None
    # Bare words (no backslash) of 3+ letters: parse_latex would split them into one-letter
    # symbols ("frac" → f·r·a·c) and produce a plausible-looking wrong answer. Unknown words
    # are refused; known function names (sqrt, abs...) go only to the fallback, which knows them.
    bare = re.findall(r'(?<![\\a-zA-Z])[a-zA-Z]{3,}', re.sub(r'\\text\s*\{[^}]*\}', ' ', s))
    if any(word.lower() not in _FALLBACK_NAMES for word in bare):
        return None
    parsers = (_sympify_fallback,) if bare else (parse_latex, _sympify_fallback)
    # `i` is the imaginary unit, except where it is an index (sums, products)
    imaginary = not re.search(r'\\(sum|prod)', s)
    for parser in parsers:
        try:
            expr = fix_constants(parser(s), imaginary)
        except Exception as e:
            logger.debug(f"{parser.__name__} failed for {s!r}: {e}")
            continue
        if _misread(expr):
            logger.debug(f"{parser.__name__} misread {s!r} as {expr}")
            continue
        return expr
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


def satisfies(eq, subs: dict, tol: float = 1e-9) -> bool | None:
    """
    Check a candidate solution against the ORIGINAL equation with 30-digit arithmetic.
    False also when a real candidate takes a side out of the real numbers (log or
    square root of a negative): that is how extraneous solutions are detected.
    None when it cannot be decided (symbolic parameters left).
    """
    try:
        lhs = sp.N(eq.lhs.subs(subs), 30)
        rhs = sp.N(eq.rhs.subs(subs), 30)
    except Exception:
        return None
    if not (lhs.is_number and rhs.is_number):
        return None
    if any(side.has(sp.nan, sp.zoo, sp.oo, -sp.oo) for side in (lhs, rhs)):
        return False
    real_candidate = all(getattr(v, "is_real", False) for v in subs.values())
    if real_candidate and (abs(sp.im(lhs)) > tol or abs(sp.im(rhs)) > tol):
        return False
    return bool(abs(lhs - rhs) <= tol * (1 + abs(lhs)))


def same_function(f, g, var, samples=(-1.7, -0.6, 0.35, 1.3, 2.9)) -> bool | None:
    """Numeric spot check that two expressions agree (used when simplify() cannot decide)."""
    checked = 0
    for p in samples:
        try:
            a, b = complex(sp.N(f.subs(var, p), 20)), complex(sp.N(g.subs(var, p), 20))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if not (abs(a) < 1e12 and abs(b) < 1e12):
            continue
        if abs(a - b) > 1e-7 * (1 + abs(a)):
            return False
        checked += 1
    return True if checked >= 2 else None


def syntax_hint(latex_expr: str) -> str | None:
    """A concrete pointer for the most common typing mistakes, instead of a generic error."""
    s = latex_expr or ""
    if r"\placeholder" in s or "#?" in s:
        return "Quedó un cuadradito vacío en el ejercicio: completalo y volvé a resolver."
    if s.count("{") != s.count("}"):
        return "Hay llaves `{ }` sin cerrar: cada `{` necesita su `}`."
    if s.count("(") != s.count(")"):
        return "Hay paréntesis sin cerrar: cada `(` necesita su `)`."
    if re.search(r"\\frac\s*\{[^{}]*\}(?!\s*\{)", s):
        return (r"A `\frac` le falta una parte: se escribe `\frac{numerador}{denominador}`, por ejemplo `\frac{1}{x}`. "
                r"Si querías una integral, probá `\int \arctan(x) dx` o elegí la operación **Integrar**.")
    return None


def error_result(latex_expr: str, hint: str = None) -> dict:
    steps = [
        "No se pudo interpretar la expresión matemática.",
        "Verificá que esté correctamente escrita en LaTeX.",
        f"Expresión recibida: `{latex_expr}`",
    ]
    # A concrete syntax problem (empty box, missing brace) says more than a generic example
    hint = syntax_hint(latex_expr) or hint
    if hint:
        steps.append(hint)
    return {
        "symbolic": latex_expr,
        "final_latex": r"\text{No se pudo interpretar la expresión}",
        "steps": steps,
        "show_graph": False,
        "ok": False,
    }


def unsolved_result(symbolic, steps: list[str], reason: str) -> dict:
    """The expression was understood but the solver failed: say so instead of claiming 'no solution'."""
    return {
        "symbolic": str(symbolic),
        "final_latex": r"\text{No se pudo resolver}",
        "steps": steps + [reason],
        "show_graph": False,
        "ok": False,
    }
