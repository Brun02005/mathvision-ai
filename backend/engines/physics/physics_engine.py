"""
Physics solver: a formula plus known data, solving for the unknown.

    F = m a, m = 10 \\text{kg}, a = 5 \\text{m/s^2}
    v = v_0 + a t; v_0 = 2; a = 3; t = 4

Recognizes common formulas (kinematics, dynamics, energy, electricity) to
name the law being applied. Values are assumed to be in SI units.
"""
import re
import logging

import sympy as sp

from engines.math.common import clean_latex, parse_math, split_top_level, error_result

logger = logging.getLogger(__name__)

# frozenset of symbol names → (law, area)
KNOWN_FORMULAS = {
    frozenset({"F", "m", "a"}): ("Segunda ley de Newton $F = m\\,a$", "Dinámica"),
    frozenset({"v", "v_{0}", "a", "t"}): ("Velocidad en MRUV $v = v_0 + a\\,t$", "Cinemática"),
    frozenset({"x", "x_{0}", "v_{0}", "a", "t"}): ("Posición en MRUV $x = x_0 + v_0 t + \\frac{1}{2} a t^2$", "Cinemática"),
    frozenset({"x", "v_{0}", "a", "t"}): ("Posición en MRUV $x = v_0 t + \\frac{1}{2} a t^2$", "Cinemática"),
    frozenset({"v", "v_{0}", "a", "x"}): ("Ecuación de Torricelli $v^2 = v_0^2 + 2 a \\Delta x$", "Cinemática"),
    frozenset({"x", "v", "t"}): ("Movimiento rectilíneo uniforme $x = v\\,t$", "Cinemática"),
    frozenset({"d", "v", "t"}): ("Movimiento rectilíneo uniforme $d = v\\,t$", "Cinemática"),
    frozenset({"E", "m", "c"}): ("Equivalencia masa-energía $E = m c^2$", "Física moderna"),
    frozenset({"K", "m", "v"}): ("Energía cinética $K = \\frac{1}{2} m v^2$", "Energía"),
    frozenset({"E_{c}", "m", "v"}): ("Energía cinética $E_c = \\frac{1}{2} m v^2$", "Energía"),
    frozenset({"U", "m", "g", "h"}): ("Energía potencial gravitatoria $U = m g h$", "Energía"),
    frozenset({"E_{p}", "m", "g", "h"}): ("Energía potencial gravitatoria $E_p = m g h$", "Energía"),
    frozenset({"W", "F", "d"}): ("Trabajo de una fuerza constante $W = F\\,d$", "Energía"),
    frozenset({"P", "W", "t"}): ("Potencia media $P = \\frac{W}{t}$", "Energía"),
    frozenset({"p", "m", "v"}): ("Cantidad de movimiento $p = m\\,v$", "Dinámica"),
    frozenset({"P", "F", "A"}): ("Presión $P = \\frac{F}{A}$", "Fluidos"),
    frozenset({"V", "I", "R"}): ("Ley de Ohm $V = I\\,R$", "Electricidad"),
    frozenset({"P", "V", "I"}): ("Potencia eléctrica $P = V\\,I$", "Electricidad"),
    frozenset({"F", "k", "x"}): ("Ley de Hooke $F = k\\,x$", "Dinámica"),
    frozenset({"P", "V", "n", "R", "T"}): ("Ley de los gases ideales $PV = nRT$", "Termodinámica"),
    frozenset({"Q", "m", "c", "T"}): ("Calor sensible $Q = m c \\Delta T$", "Termodinámica"),
}

_UNIT = re.compile(r"\\(?:text|mathrm|,?\s*\\mathrm|operatorname)\{([^}]*)\}")
_DATA = re.compile(r"^\s*([A-Za-z](?:_\{?[A-Za-z0-9]+\}?)?)\s*=\s*(-?[\d.,]+(?:\s*\\cdot\s*10\^\{?-?\d+\}?)?(?:e-?\d+)?)\s*(.*)$")


def _strip_units(s: str) -> tuple[str, str]:
    units = " ".join(u.strip() for u in _UNIT.findall(s))
    return _UNIT.sub("", s).strip(), units


def split_formula_and_data(latex_expr: str):
    """Return (formula, [(name, value_str, unit)]) or None if it does not look like formula + data."""
    parts = split_top_level(clean_latex(latex_expr), seps=(",", ";"))
    if len(parts) < 2 or "=" not in parts[0]:
        return None
    data = []
    for p in parts[1:]:
        m = _DATA.match(p)
        if not m:
            return None
        value, unit = _strip_units(m.group(2) + " " + m.group(3))
        data.append((m.group(1), value, unit))
    return parts[0], data


def looks_like_physics(latex_expr: str) -> bool:
    split = split_formula_and_data(latex_expr)
    if not split:
        return False
    formula, data = split
    if any(unit for _, _, unit in data) or _UNIT.search(formula):
        return True
    eq = _parse_eq(formula)
    return eq is not None and _identify(eq) is not None


def _parse_eq(formula: str):
    formula, _ = _strip_units(formula)
    if "=" not in formula:
        return None
    lhs_s, rhs_s = formula.split("=", 1)
    lhs, rhs = parse_math(lhs_s), parse_math(rhs_s)
    return sp.Eq(lhs, rhs) if lhs is not None and rhs is not None else None


def _identify(eq):
    names = frozenset(s.name for s in eq.free_symbols)
    return KNOWN_FORMULAS.get(names)


def solve_physics(latex_expr: str, sub_domain: str = "Física") -> dict:
    split = split_formula_and_data(latex_expr)
    if not split:
        return error_result(latex_expr, "Formato esperado: fórmula seguida de los datos, p. ej. `F = m a, m = 10, a = 5`")
    formula, data = split
    eq = _parse_eq(formula)
    if eq is None:
        return error_result(latex_expr)

    symbols = {s.name: s for s in eq.free_symbols}
    known, units = {}, {}
    for name, value_s, unit in data:
        value = parse_math(value_s.replace(",", "."))
        sym = symbols.get(name) or symbols.get(re.sub(r"_(\w)$", r"_{\1}", name))
        if sym is None or value is None:
            continue
        known[sym] = value
        if unit:
            units[sym] = unit

    unknowns = [s for s in eq.free_symbols if s not in known]
    law = _identify(eq)

    steps = []
    if law:
        steps.append(f"Problema de **{law[1]}**. Aplicamos: {law[0]}.")
    steps.append(f"Fórmula: $${sp.latex(eq)}$$")
    if known:
        data_l = ",\\quad ".join(
            f"{sp.latex(k)} = {sp.latex(v)}" + (f"\\,\\text{{{units[k]}}}" if k in units else "")
            for k, v in known.items())
        steps.append(f"**Datos:** $${data_l}$$")
    steps.append("Trabajamos en unidades del **Sistema Internacional (SI)**; si algún dato viene en otra unidad, convertilo antes.")

    if len(unknowns) != 1:
        names = ", ".join(f"${sp.latex(u)}$" for u in unknowns) or "ninguna"
        steps.append(f"Incógnitas sin dato: {names}. Para despejar hace falta que quede **exactamente una**.")
        return {"symbolic": str(eq), "final_latex": r"\text{Faltan datos}", "steps": steps, "show_graph": False}

    target = unknowns[0]
    t_l = sp.latex(target)
    try:
        isolated = sp.solve(eq, target)
    except Exception as e:
        logger.warning(f"physics solve failed: {e}")
        isolated = []
    if not isolated:
        return {"symbolic": str(eq), "final_latex": r"\text{Sin solución}",
                "steps": steps + ["No se pudo despejar la incógnita."], "show_graph": False}

    isolated_l = r",\; ".join(sp.latex(i) for i in isolated)
    steps.append(f"Despejamos ${t_l}$: $${t_l} = {isolated_l}$$")

    values = [sp.nsimplify(sp.simplify(i.subs(known))) for i in isolated]
    # Physical magnitudes like time, mass or distance are usually non-negative
    positive = [v for v in values if v.is_real and v >= 0]
    if len(values) > 1 and positive:
        if len(positive) < len(values):
            steps.append("Descartamos las soluciones negativas por no tener sentido físico.")
        values = positive

    subst_l = sp.latex(isolated[0].subs(known, simultaneous=True)) if len(isolated) == 1 else None
    if subst_l:
        steps.append(f"Sustituimos los datos: $${t_l} = {subst_l}$$")

    val_l = ",\\; ".join(
        sp.latex(v) + (f" \\approx {sp.latex(sp.N(v, 5))}" if v.is_number and not v.is_Rational else "")
        for v in values)
    steps.append(f"**Resultado:** $${t_l} = {val_l}$$")
    return {
        "symbolic": str(eq),
        "final_latex": f"{t_l} = {val_l}",
        "steps": steps,
        "show_graph": False,
    }
