import logging
import sys
import time
from collections import Counter, defaultdict

from benchmark import run_all


def main() -> int:
    logging.disable(logging.CRITICAL)
    outcomes = run_all()

    by_topic = defaultdict(list)
    for o in outcomes:
        by_topic[o.case.topic].append(o)

    print(f"{'Tema':<28}{'Aciertos':>10}{'%':>7}{'Verificados':>13}{'Tiempo máx.':>13}")
    print("-" * 71)
    for topic, items in by_topic.items():
        ok = sum(o.passed for o in items)
        verified = sum(o.verified is True for o in items)
        slowest = max(o.seconds for o in items)
        print(f"{topic:<28}{ok:>5}/{len(items):<4}{100 * ok / len(items):>6.0f}%{verified:>9}/{len(items):<3}{slowest:>11.2f}s")
    total_ok = sum(o.passed for o in outcomes)
    print("-" * 71)
    print(f"{'TOTAL':<28}{total_ok:>5}/{len(outcomes):<4}{100 * total_ok / len(outcomes):>6.1f}%")

    unexpected = [o for o in outcomes if not o.passed and not o.case.xfail]
    known = [o for o in outcomes if not o.passed and o.case.xfail]
    fixed = [o for o in outcomes if o.passed and o.case.xfail]
    if known:
        print(f"\nLimitaciones conocidas ({len(known)}):")
        for o in known:
            print(f"  · [{o.case.topic}] {o.case.latex} — {o.case.xfail}")
    if fixed:
        print(f"\nMarcados como limitación pero ya resueltos ({len(fixed)}): quitarles el xfail.")
        for o in fixed:
            print(f"  · [{o.case.topic}] {o.case.latex}")
    if unexpected:
        print(f"\nFALLAS ({len(unexpected)}):")
        for o in unexpected:
            print(f"  ✗ [{o.case.topic}] {o.case.latex}\n      {o.detail}")
    return 1 if unexpected else 0


def main_ai() -> int:
    """Word problems and free text through the full pipeline, including the AI tiers."""
    logging.disable(logging.CRITICAL)
    from interpreter import llm
    if not llm.available():
        print("El banco de IA necesita GEMINI_API_KEY (en backend/.env). No se corrió: no hay resultados que informar.")
        return 2

    import config
    import pipeline
    from benchmark.cases_ai import AI_CASES
    from benchmark.compare import contains_answer

    config.SOLVER_WORKERS = 0  # in-process: one exercise at a time, no worker pool needed
    rows = []
    for case in AI_CASES:
        start = time.monotonic()
        try:
            res = pipeline.solve(case.latex)
        except Exception as e:
            res = {"solved": False, "method": None, "final_result_latex": f"error: {e}"}
        passed = bool(res.get("solved")) and contains_answer(res.get("answer"), case.expected, case.kind)
        rows.append((case, res, passed, time.monotonic() - start))
        mark = "✓" if passed else "✗"
        print(f"{mark} {res.get('method') or '-':<12} {'verif.' if res.get('verified') else '':<7} "
              f"{time.monotonic() - start:5.1f}s  {case.latex[:70]}")
        if not passed:
            print(f"      esperado {case.expected}, obtenido {res.get('final_result_latex', '')[:80]}")

    ok = sum(p for _, _, p, _ in rows)
    methods = Counter(r.get("method") for _, r, _, _ in rows if r.get("solved"))
    unsolved = sum(1 for _, r, _, _ in rows if not r.get("solved"))
    wrong_verified = [c for c, r, p, _ in rows if not p and r.get("verified")]
    print(f"\nAciertos: {ok}/{len(rows)} ({100 * ok / len(rows):.0f}%)")
    print(f"Resueltos por: motor exacto {methods['symbolic']}, IA traduce + motor {methods['interpreted']}, "
          f"solo IA {methods['ai']}, sin resolver {unsolved}")
    print(f"Incorrectos con sello 'Verificado': {len(wrong_verified)} (tiene que ser 0)")
    return 1 if wrong_verified else 0


if __name__ == "__main__":
    sys.exit(main_ai() if "--ai" in sys.argv else main())
