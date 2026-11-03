"""
Pedagogical layer: frames the solver's raw steps the way a professor would,
with an introduction per topic and a closing tip.
"""

INTROS = {
    "Aritmética": "Resolvamos la cuenta respetando la jerarquía de operaciones.",
    "Álgebra": "Abordemos esta expresión algebraica paso a paso.",
    "Inecuaciones": "En una inecuación buscamos un conjunto de valores, no un único número.",
    "Sistemas de Ecuaciones": "Buscamos los valores que satisfacen todas las ecuaciones a la vez.",
    "Análisis de Funciones": "Análisis completo: dominio, paridad, cortes con los ejes, continuidad, asíntotas, "
                             "crecimiento y extremos, concavidad e inflexión, positividad e imagen.",
    "Trigonometría": "Usaremos identidades y valores notables de las funciones trigonométricas.",
    "Ecuaciones Trigonométricas": "Resolvemos la ecuación recordando que las funciones trigonométricas son periódicas.",
    "Límites": "Analicemos a qué valor se acerca la función, atentos a posibles indeterminaciones.",
    "Cálculo Diferencial": "Para resolver esta derivada, aplicaremos las reglas de derivación correspondientes.",
    "Cálculo Integral": "Comencemos analizando la estructura del integrando para elegir la técnica adecuada.",
    "Series y Sucesiones": "Estudiemos el término general para decidir si la serie converge y, si es posible, su suma.",
    "Ecuaciones Diferenciales": "Primero identificamos el tipo de ecuación diferencial; eso determina el método.",
    "Álgebra Lineal": "Analicemos las propiedades de las matrices dadas.",
    "Física": "Identifiquemos la ley física, los datos y la incógnita.",
    "Números Complejos": "Trabajamos con números de la forma a + bi, donde i² = −1.",
    "Estadística": "Resumamos los datos con medidas de posición y de dispersión.",
    "Vectores": "Operamos con los vectores componente a componente.",
}

TIPS = {
    "Cálculo Integral": "Tip: podés verificar cualquier primitiva derivándola.",
    "Cálculo Diferencial": "Tip: antes de derivar, conviene simplificar la expresión si es posible.",
    "Límites": "Tip: si al sustituir aparece 0/0 o ∞/∞, probá factorizar, racionalizar o L'Hôpital.",
    "Ecuaciones Diferenciales": "Tip: sustituí la solución en la ecuación para verificarla.",
    "Física": "Tip: revisá que las unidades del resultado sean coherentes con la magnitud buscada.",
    "Inecuaciones": "Tip: al multiplicar o dividir por un número negativo, el sentido de la desigualdad se invierte.",
    "Estadística": "Tip: si los datos son una muestra, usá el desvío muestral (dividiendo por n − 1).",
}


def enhance_explanation(domain: str, raw_steps: list) -> list:
    if not raw_steps:
        return ["No se pudieron generar pasos detallados para este problema."]

    intro = INTROS.get(domain, "Vamos a resolver este problema paso a paso.")
    steps = [f"**Nota del Profesor:** {intro}", *raw_steps]
    tip = TIPS.get(domain)
    if tip:
        steps.append(tip)
    return steps
