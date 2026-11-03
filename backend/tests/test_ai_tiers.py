"""
The three tiers: exact engine → AI translates + engine solves → AI solves (labeled).
The AI is replaced by fakes: these tests check the orchestration and the honesty of
the result (method, verified), not the model's quality.
"""
import pytest

import pipeline
from interpreter import llm
from interpreter.llm import AISolution, Translation

WORD_PROBLEM = "Un tren recorre 120 km en 2 horas. ¿Cuál es su velocidad media?"


@pytest.fixture
def fake_ai(monkeypatch):
    state = {"translation": None, "solution": None, "calls": []}
    monkeypatch.setattr(llm, "available", lambda: True)

    def translate(text, operation="auto"):
        state["calls"].append("translate")
        return state["translation"]

    def solve(text):
        state["calls"].append("solve")
        return state["solution"]

    monkeypatch.setattr(llm, "translate", translate)
    monkeypatch.setattr(llm, "solve", solve)
    return state


def test_exact_engine_first_and_no_ai_call(fake_ai):
    res = pipeline.solve("x^2 = 4")
    assert res["method"] == "symbolic" and res["verified"] is True
    assert fake_ai["calls"] == []


def test_word_problem_is_translated_and_solved_by_the_engine(fake_ai):
    fake_ai["translation"] = Translation(kind="math", latex=r"v = \frac{d}{t}, d = 120, t = 2",
                                         operation="auto", reading="velocidad = distancia / tiempo")
    res = pipeline.solve(WORD_PROBLEM)
    assert res["method"] == "interpreted"
    assert res["final_result_latex"] == "v = 60"
    assert res["verified"] is True  # the engine verified it, not the AI
    assert res["extracted_latex"] == WORD_PROBLEM
    assert res["interpretation"] == r"v = \frac{d}{t}, d = 120, t = 2"
    assert "Cómo entendimos" in res["steps"][0]
    assert fake_ai["calls"] == ["translate"]


def test_ai_solves_when_engine_cannot_and_is_labeled(fake_ai):
    fake_ai["solution"] = AISolution(topic="Probabilidad", steps=["Casos favorables sobre posibles: $\\frac{1}{6}$"],
                                     final_latex=r"\frac{1}{6}", answer_sympy="1/6")
    res = pipeline.solve("¿Cuál es la probabilidad de sacar un 3 al tirar un dado?")
    assert res["method"] == "ai" and res["solved"] is True
    assert res["verified"] is None  # never the verified badge
    assert "Resuelto con IA" in res["steps"][0]  # the label is part of the saved steps
    assert fake_ai["calls"] == ["translate", "solve"]


def test_translation_the_engine_cannot_solve_falls_back_to_ai(fake_ai):
    fake_ai["translation"] = Translation(kind="math", latex=r"\frac{{", operation="auto", reading="?")
    fake_ai["solution"] = AISolution(topic="Geometría", steps=["paso"], final_latex="12")
    res = pipeline.solve("El área de un rectángulo de lados 3 y 4")
    assert res["method"] == "ai" and res["final_result_latex"] == "12"


def test_not_math_is_reported(fake_ai):
    fake_ai["translation"] = Translation(kind="not_math", latex="", operation="auto", reading="")
    res = pipeline.solve("Hola, ¿cómo estás hoy?")
    assert res["solved"] is False and fake_ai["calls"] == ["translate"]


def test_nobody_can_solve_it_says_so(fake_ai):
    res = pipeline.solve(WORD_PROBLEM)
    assert res["solved"] is False  # never an invented answer
    assert fake_ai["calls"] == ["translate", "solve"]


def test_without_ai_word_problems_explain_why(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    res = pipeline.solve(WORD_PROBLEM)
    assert res["solved"] is False
    assert "asistente de IA" in " ".join(res["steps"])


def test_invalid_model_output_is_rejected_and_failures_are_not_cached(monkeypatch):
    calls = []

    def ask(prompt, content, schema, timeout_ms):
        calls.append(1)
        return Translation(kind="math", latex="x = 1", operation="rm -rf", reading="")

    monkeypatch.setattr(llm, "_ask", ask)
    llm.translate.cache_clear()
    assert llm.translate("algo raro") is None
    assert llm.translate("algo raro") is None
    assert len(calls) == 2  # a rejected/failed answer is retried, not remembered


def test_successful_translations_are_cached(monkeypatch):
    calls = []

    def ask(prompt, content, schema, timeout_ms):
        calls.append(1)
        return Translation(kind="math", latex="x = 1", operation="solve", reading="")

    monkeypatch.setattr(llm, "_ask", ask)
    llm.translate.cache_clear()
    llm.translate("mismo ejercicio")
    llm.translate("mismo ejercicio")
    assert len(calls) == 1


def test_api_reports_the_method(fake_ai):
    from fastapi.testclient import TestClient

    from main import app
    fake_ai["translation"] = Translation(kind="math", latex=r"v = \frac{d}{t}, d = 120, t = 2",
                                         operation="auto", reading="v = d/t")
    body = TestClient(app).post("/api/solve-text", data={"latex_expression": WORD_PROBLEM}).json()
    assert body["method"] == "interpreted" and body["interpretation"]


def test_history_keeps_the_ai_label(fake_ai):
    from fastapi.testclient import TestClient

    from main import app
    fake_ai["solution"] = AISolution(topic="Geometría", steps=["Área = base · altura"], final_latex="12")
    client = TestClient(app)
    created = client.post("/api/solve-text", data={"latex_expression": "El área de un rectángulo de lados 3 y 4",
                                                   "mode": "Exam"}).json()
    assert created["method"] == "ai"
    assert client.get(f"/api/history/{created['id']}").json()["method"] == "ai"
