"""
What the user wants done with the expression. The expression alone does not say
it: x^3 - 8 can mean "factor it", "solve x^3 - 8 = 0" or "study the function".

The operation comes from, in order of priority:
1. the operation chosen explicitly in the UI / API (`operation` parameter);
2. a command written in the exercise: "factorizar x^3 - 8", "\\text{Taylor de } e^x";
3. "auto": the domain classifier decides from the structure of the expression.
"""
import re
from dataclasses import dataclass, field

AUTO = "auto"
SOLVE = "solve"
SIMPLIFY = "simplify"
FACTOR = "factor"
EXPAND = "expand"
PARTIAL_FRACTIONS = "partial_fractions"
DERIVATIVE = "derivative"
INTEGRAL = "integral"
TAYLOR = "taylor"
ANALYZE = "analyze"
STATISTICS = "statistics"

OPERATIONS = (AUTO, SOLVE, SIMPLIFY, FACTOR, EXPAND, PARTIAL_FRACTIONS,
              DERIVATIVE, INTEGRAL, TAYLOR, ANALYZE, STATISTICS)

# Longer alternatives first: the regex engine takes the first one that matches
_COMMANDS = [
    (TAYLOR, r"(?:serie|polinomio|desarrollo)\s+de\s+(?:taylor|maclaurin)|taylor|maclaurin"),
    (PARTIAL_FRACTIONS, r"fracciones\s+(?:parciales|simples)|partial\s+fractions?"),
    (FACTOR, r"descomponer\s+en\s+(?:factores\s+)?primos|factorizaci[oó]n|factoriz(?:ar|[aá])|factorise|factorize|factor"),
    (EXPAND, r"desarrollar|desarroll[aá]|expandir|expand[ií]|expand|aplicar\s+distributiva|distributiva"),
    (SIMPLIFY, r"simplificar|simplific[aá]|simplify|reducir|reduc[ií]"),
    (DERIVATIVE, r"derivada\s+de|derivada|derivar|deriv[aá]|derivative\s+of|differentiate"),
    (INTEGRAL, r"integral\s+de|integrar|integr[aá]|integrate|primitiva\s+de|antiderivada\s+de"),
    (ANALYZE, r"(?:analizar|analiz[aá]|estudiar|estudi[aá]|an[aá]lisis(?:\s+completo)?\s+de|estudio(?:\s+completo)?\s+de)"
              r"(?:\s+(?:la\s+)?funci[oó]n)?"),
    (STATISTICS, r"desv[ií]o\s+est[aá]ndar|desviaci[oó]n\s+est[aá]ndar|media|promedio|mediana|moda|varianza"
                 r"|desv[ií]o|desviaci[oó]n|estad[ií]sticas?|mean|median|variance"),
    (SOLVE, r"resolver|resolv[eé]|solve|hallar|hall[aá]|encontrar|encontr[aá]|calcular|calcul[aá]"),
]

_STATS = {
    "media": "mean", "promedio": "mean", "mean": "mean", "mediana": "median", "median": "median",
    "moda": "mode", "varianza": "variance", "variance": "variance",
}

_LEAD = re.compile(
    r"^\s*(?:\\(?:text|mathrm|textbf)\s*\{\s*)?"
    r"(?P<cmd>" + "|".join(f"(?:{p})" for _, p in _COMMANDS) + r")\b"
    r"(?:\s+(?:de|del|la|el|los|las|of|the|funci[oó]n|expresi[oó]n|ecuaci[oó]n|polinomio|datos)\b)*"
    r"\s*\}?\s*:?\s*",
    re.IGNORECASE,
)


@dataclass
class Intent:
    operation: str
    body: str
    params: dict = field(default_factory=dict)


def _operation_for(command: str) -> str:
    for op, pattern in _COMMANDS:
        if re.fullmatch(pattern, command, re.IGNORECASE):
            return op
    return AUTO


def detect_intent(latex: str, operation: str = AUTO) -> Intent:
    """Split a leading command off the expression. The explicit `operation` wins over the command."""
    s = latex.strip()
    params = {}
    m = _LEAD.match(s)
    if m:
        command = re.sub(r"\s+", " ", m.group("cmd").lower())
        found = _operation_for(command)
        if found == STATISTICS:
            # Longest name first: "mediana" also starts with "media"
            params["stat"] = next((_STATS[k] for k in sorted(_STATS, key=len, reverse=True)
                                   if command.startswith(k)), None)
            if "desv" in command:
                params["stat"] = "std"
        s = s[m.end():].strip()
        if operation == AUTO:
            operation = found
    return Intent(operation, s, params)
