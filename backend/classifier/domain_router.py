import re

def classify_domain(latex_expression: str) -> str:
    """
    Heuristics-based domain classifier for mathematical expressions.
    Classifies into: "Álgebra", "Cálculo Diferencial", "Cálculo Integral", 
    "Ecuaciones Diferenciales", "Álgebra Lineal", etc.
    """
    latex_lower = latex_expression.lower()
    
    if "\\int" in latex_lower:
        return "Cálculo Integral"
    if "d/d" in latex_lower or "\\frac{d}{d" in latex_lower or "\\partial" in latex_lower or "'" in latex_lower:
        # Simple heuristic to distinguish ODEs from pure derivatives
        if "=" in latex_lower and ("y" in latex_lower or "f" in latex_lower):
            return "Ecuaciones Diferenciales"
        return "Cálculo Diferencial"
    if "\\lim" in latex_lower:
        return "Cálculo Diferencial"
    if "\\sum" in latex_lower:
        return "Series y Sucesiones"
    if "\\begin{pmatrix}" in latex_lower or "\\begin{bmatrix}" in latex_lower or "\\det" in latex_lower:
        return "Álgebra Lineal"
    if "\\sin" in latex_lower or "\\cos" in latex_lower or "\\tan" in latex_lower:
        # Could be Trig or Algebra with Trig, default to Trigonometría if no other match
        if "=" in latex_lower:
            return "Ecuaciones Trigonométricas"
        return "Trigonometría"
    
    return "Álgebra"
