import pytest

from classifier import domain_router as dr


@pytest.mark.parametrize("latex,domain", [
    (r"\int x^2 dx", dr.INTEGRAL),
    (r"\begin{pmatrix} 1 & 0 \\ 0 & 1 \end{pmatrix}", dr.LINEAR_ALGEBRA),
    (r"\det \begin{pmatrix} 1 & 0 \\ 0 & 1 \end{pmatrix}", dr.LINEAR_ALGEBRA),
    (r"\sum_{n=1}^{\infty} \frac{1}{n^2}", dr.SERIES),
    (r"\lim_{x \to 0} \frac{\sin x}{x}", dr.LIMIT),
    (r"\frac{d}{dx}(x^3)", dr.DERIVATIVE),
    (r"\frac{d^2}{dx^2}(x^3)", dr.DERIVATIVE),
    (r"f'(x) = x^2 \sin(x)", dr.DERIVATIVE),
    (r"y' = 2y", dr.ODE),
    (r"\frac{dy}{dx} = x y", dr.ODE),
    (r"y'' + y = 0, y(0) = 1, y'(0) = 0", dr.ODE),
    (r"F = m a, m = 10, a = 5", dr.PHYSICS),
    (r"d = v t, v = 3 \text{m/s}, t = 2 \text{s}", dr.PHYSICS),
    (r"2x + y = 5; x - y = 1", dr.SYSTEM),
    (r"x^2 - 4 > 0", dr.INEQUALITY),
    (r"f(x) = x^2 - 1", dr.FUNCTION),
    (r"\sin(x) = \frac{1}{2}", dr.TRIG_EQUATION),
    (r"\sin^2(x) + \cos^2(x)", dr.TRIG),
    (r"2 + 2", dr.ARITHMETIC),
    (r"\frac{3}{4} + \frac{1}{8}", dr.ARITHMETIC),
    (r"x^2 - 5x + 6 = 0", dr.ALGEBRA),
])
def test_domain_classifier(latex, domain):
    assert dr.classify_domain(latex) == domain


@pytest.mark.parametrize("text, operation, body", [
    ("factorizar x^3 - 8", "factor", "x^3 - 8"),
    (r"\text{Factorizá} x^2 - 1", "factor", "x^2 - 1"),
    (r"\text{Taylor de } e^{x} \text{ en } x = 0", "taylor", r"e^{x} \text{ en } x = 0"),
    ("derivada de x^2", "derivative", "x^2"),
    ("media de 1, 2, 3", "statistics", "1, 2, 3"),
    ("x^2 - 4", "auto", "x^2 - 4"),
    ("factorial(5)", "auto", "factorial(5)"),
])
def test_intent_detection(text, operation, body):
    from classifier.intent import detect_intent
    it = detect_intent(text)
    assert (it.operation, it.body) == (operation, body)


def test_explicit_operation_wins_over_command():
    from classifier.intent import detect_intent
    assert detect_intent("factorizar x^2 - 4", "solve").operation == "solve"


@pytest.mark.parametrize("text, expected", [
    ("cuánto es 2 más 3 por 4", r"2 + 3 \cdot 4"),
    ("x al cuadrado menos 4 igual a 0", "x^{2} - 4 = 0"),
    ("raíz cuadrada de 16 más 2", r"\sqrt{16} + 2"),
    ("seno de pi sobre 2", r"\sin(\pi/2)"),
    ("logaritmo en base 2 de 32", r"\log_{2}(32)"),
    # Not understood → unchanged, so it goes to the AI instead of becoming a wrong formula
    ("el doble de un número es 10", "el doble de un número es 10"),
    (r"\int x^2 dx", r"\int x^2 dx"),
])
def test_natural_language_math(text, expected):
    from interpreter.natural import to_math
    assert to_math(text) == expected
