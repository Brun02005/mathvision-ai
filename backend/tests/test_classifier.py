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
