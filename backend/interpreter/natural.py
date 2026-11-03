"""
Spanish math in words → math notation, without AI:

    "cuánto es 2 más 3 por 4"           → 2 + 3 \\cdot 4
    "raíz cuadrada de 16 más 2"         → \\sqrt{16} + 2
    "x al cuadrado menos 4 igual a 0"   → x^{2} - 4 = 0
    "seno de pi sobre 2"                → \\sin(\\pi) / 2

Deliberately conservative: if any word is left that it does not understand, it
returns the input unchanged and the exercise goes to the AI interpreter (or is
rejected). Guessing here would turn a word problem into a wrong formula.
"""
import re
import unicodedata

from engines.math.common import natural_language_words

_NUMBERS = {
    "cero": 0, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "treinta": 30,
    "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
    "cien": 100, "mil": 1000,
}

# A simple operand right after "raíz de", "seno de", ...: (group), number, \pi or a variable
_OPERAND = r"(\([^()]*\)|-?\d+(?:\.\d+)?|\\pi|[a-z](?![a-z]))"

# Order matters: longer phrases before the words they contain ("dividido por" before "por")
_RULES = [
    (r"^\s*(?:cuanto (?:es|da|vale)|calcula(?:r)?|calcule|resolve|resuelve|resolver)\s+", ""),
    (r"\bpi\b", r"\\pi"),
    (r"\bpor ?ciento\b", r"\\%"),
    # "seno de pi sobre 2" is sin(π/2): angles are said as fractions. Only for trig functions;
    # "raíz de 16 sobre 4" is genuinely ambiguous, so it is left as written.
    (r"\b((?:seno|sen|coseno|tangente) de)\s*(\\pi|\d+)\s+(?:sobre|dividido (?:por|entre))\s+(\d+)\b", r"\1 (\2/\3)"),
    (r"\braiz cuadrada de\s*" + _OPERAND, r"\\sqrt{\1}"),
    (r"\braiz cubica de\s*" + _OPERAND, r"\\sqrt[3]{\1}"),
    (r"\braiz de\s*" + _OPERAND, r"\\sqrt{\1}"),
    (r"\blogaritmo natural de\s*" + _OPERAND, r"\\ln(\1)"),
    (r"\blogaritmo en base\s*(\d+)\s*de\s*" + _OPERAND, r"\\log_{\1}(\2)"),
    (r"\blogaritmo de\s*" + _OPERAND, r"\\log(\1)"),
    (r"\barco ?tangente de\s*" + _OPERAND, r"\\arctan(\1)"),
    (r"\barco ?seno de\s*" + _OPERAND, r"\\arcsin(\1)"),
    (r"\barco ?coseno de\s*" + _OPERAND, r"\\arccos(\1)"),
    (r"\b(?:seno|sen) de\s*" + _OPERAND, r"\\sin(\1)"),
    (r"\bcoseno de\s*" + _OPERAND, r"\\cos(\1)"),
    (r"\btangente de\s*" + _OPERAND, r"\\tan(\1)"),
    (r"\s*\bal cuadrado\b", "^{2}"),
    (r"\s*\bal cubo\b", "^{3}"),
    (r"\s*\belevado (?:a la|a)\s*(\d+|[a-z])\b", r"^{\1}"),
    (r"\s+a la\s+(\d+|[a-z](?![a-z])|\([^()]*\))", r"^{\1}"),  # "e a la x", "2 a la 3"
    (r"\bmultiplicado por\b", r"\\cdot"),
    (r"\bdividido (?:por|entre)\b", "/"),
    (r"\b(?:sobre|entre)\b", "/"),
    (r"\b(?:por|veces)\b", r"\\cdot"),
    (r"\bmas\b", "+"),
    (r"\bmenos\b", "-"),
    (r"\b(?:es )?mayor o igual (?:que|a)\b", r"\\geq"),
    (r"\b(?:es )?menor o igual (?:que|a)\b", r"\\leq"),
    (r"\b(?:es )?mayor (?:que|a)\b", ">"),
    (r"\b(?:es )?menor (?:que|a)\b", "<"),
    (r"\b(?:es )?igual a\b", "="),
]


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def to_math(text: str) -> str:
    """Translate simple spoken math. Returns the input unchanged when unsure."""
    if "\\" in text and not natural_language_words(text):
        return text  # already LaTeX
    s = _strip_accents(text.lower()).strip()
    s = re.sub(r"[¿?¡]", " ", s)  # not "!": 5! is a factorial
    s = re.sub(r"(?<![\w)])!", " ", s)
    s = re.sub(r"\b(" + "|".join(_NUMBERS) + r")\b", lambda m: str(_NUMBERS[m.group(1)]), s)
    for pattern, replacement in _RULES:
        s = re.sub(pattern, replacement, s)
    s = re.sub(r"\(\(([^()]*)\)\)", r"(\1)", s)  # \sin((\pi/2)) → \sin(\pi/2)
    s = re.sub(r"\s+", " ", s).strip()
    if s == _strip_accents(text.lower()).strip() or natural_language_words(s):
        return text
    return s
