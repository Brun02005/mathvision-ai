import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engines.math import calculus, algebra
from classifier import domain_router

def test_calculus_integral():
    # Simple definite integral
    latex_expr = r"\int_{0}^{\pi} \sin(x) dx"
    result = calculus.solve_integral(latex_expr)
    assert result is not None
    assert "steps" in result
    assert "final_latex" in result

def test_algebra_equation():
    latex_expr = "x^2 - 4 = 0"
    result = algebra.solve_equation(latex_expr)
    assert "x" in result["final_latex"]
    assert "steps" in result

def test_domain_classifier():
    assert domain_router.classify_domain(r"\int x^2 dx") == "Cálculo Integral"
    assert domain_router.classify_domain(r"\begin{pmatrix} 1 & 0 \\ 0 & 1 \end{pmatrix}") == "Álgebra Lineal"
