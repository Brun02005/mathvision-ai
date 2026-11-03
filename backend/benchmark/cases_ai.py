"""
Exercises written the way people actually send them: word problems, plain text,
typos, missing symbols. They need the AI tiers, so they only run with a
GEMINI_API_KEY:  python -m benchmark --ai

kind "value": the expected value must be among the answer's values (a system
answer {x: 17, y: 13} contains 17); a set must match exactly.
Answers computed by hand.
"""
import sympy as sp
from sympy import FiniteSet, Rational, exp, pi

from benchmark.cases import Case

x = sp.Symbol("x")

AI_CASES = [
    # Word problems → the AI should only translate, the engine solves and verifies
    Case("Enunciados", "Un tren recorre 120 km en 2 horas. ¿Cuál es su velocidad media en km/h?", 60),
    Case("Enunciados", "La suma de dos números es 30 y su diferencia es 4. ¿Cuál es el mayor?", 17),
    Case("Enunciados", "Juan tiene el triple de la edad de su hijo. Dentro de 10 años tendrá el doble. ¿Qué edad tiene el hijo?", 10),
    Case("Enunciados", "Un rectángulo tiene perímetro 20 y área 24. ¿Cuánto mide el lado más largo?", 6),
    Case("Enunciados", "El 20% de un número es 50. ¿Cuál es el número?", 250),
    Case("Enunciados", "Hallar el valor de x si 2x + 5 = 17", 6),
    Case("Enunciados", "Un auto parte del reposo y acelera a 2 m/s² durante 5 segundos. ¿Qué velocidad alcanza en m/s?", 10),
    Case("Enunciados", "¿Cuánto mide la hipotenusa de un triángulo rectángulo de catetos 6 y 8?", 10),
    Case("Enunciados", "Hallar la pendiente de la recta que pasa por los puntos (1, 2) y (3, 8)", 3),
    Case("Enunciados", "Un capital de 1000 pesos se invierte al 10% anual con interés compuesto. ¿Cuánto hay al cabo de 2 años?", 1210),
    Case("Enunciados", "Calcular el área de un círculo de radio 3", 9 * pi),
    Case("Enunciados", "¿De cuántas formas se pueden elegir 3 personas de un grupo de 10?", 120),
    Case("Enunciados", "¿Cuál es la probabilidad de sacar un número par al tirar un dado?", Rational(1, 2)),
    Case("Enunciados", "Calculá la media de las notas 7, 8, 9 y 10", Rational(17, 2)),
    # Plain text and typos (as typed on a phone or read from a blurry photo)
    Case("Texto libre", "x2 - 5x + 6 = 0", FiniteSet(2, 3)),
    Case("Texto libre", "lim x->0 sin(x)/x", 1),
    Case("Texto libre", "integral de 0 a pi de sen x", 2),
    Case("Texto libre", "integral de x por e a la x", (x - 1) * exp(x), "antiderivative"),
    Case("Texto libre", "derivada de x al cubo", 3 * x**2),
    Case("Texto libre", "determinante de la matriz [[1, 2], [3, 4]]", -2),
    Case("Texto libre", "raiz cuadrada de 2 por raiz cuadrada de 8", 4),
]
