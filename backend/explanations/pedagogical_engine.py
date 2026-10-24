def enhance_explanation(domain: str, raw_steps: list) -> list:
    """
    Pedagogical engine that enhances raw solver steps with 
    professor-like explanations in Spanish based on the domain.
    """
    enhanced_steps = []
    
    if not raw_steps:
        return ["No se pudieron generar pasos detallados para este problema."]
        
    # Introduction templates based on domain
    intros = {
        "Cálculo Integral": "Comencemos analizando la estructura de la integral proporcionada.",
        "Cálculo Diferencial": "Para resolver esta derivada, aplicaremos las reglas de derivación correspondientes.",
        "Álgebra": "Abordemos esta ecuación algebraica paso a paso.",
        "Ecuaciones Diferenciales": "Resolveremos esta ecuación diferencial identificando primero su tipo (separable, lineal, exacta, etc.).",
        "Álgebra Lineal": "Analicemos las propiedades de las matrices o vectores dados.",
        "Cinemática": "Para este problema de movimiento, identificaremos primero las variables conocidas.",
        "Dinámica": "Aplicaremos las leyes de Newton para comprender las fuerzas involucradas."
    }
    
    # Add intro
    intro = intros.get(domain, "Vamos a resolver este problema matemático paso a paso.")
    enhanced_steps.append(f"**Nota del Profesor:** {intro}")
    
    # Add actual steps with pedagogical connective tissue
    for idx, step in enumerate(raw_steps):
        # Add a subtle pedagogical transition for intermediate steps
        if idx == len(raw_steps) // 2 and len(raw_steps) > 3:
            enhanced_steps.append("Llegados a este punto, simplificamos la expresión obtenida:")
        enhanced_steps.append(step)
        
    # Add conclusion
    enhanced_steps.append("Verifica el resultado final asegurándote de comprender cada transformación algebraica. ¡Buen trabajo!")
    
    return enhanced_steps
