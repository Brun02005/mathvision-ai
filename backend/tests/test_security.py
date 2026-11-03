"""
Hardening against hostile input. Untrusted text reaches SymPy's parse_expr, which uses
eval(): these tests pin each layer of safe_parse_expr independently, plus the limits on
images, PDFs, stored photos and worker environment.
"""
import io
import os

import pymupdf
import pytest
from PIL import Image

from engines.math.common import UnsafeExpression, parse_math, safe_parse_expr
from engines.math.linear_algebra import solve_linear_algebra
from pipeline import run_solver

# Layers 1 and 2: refused before any evaluation
PAYLOADS = [
    "__import__('os').system('echo pwned')",
    "x.__class__.__mro__",
    "(1).__class__",
    "open('/etc/passwd')",
    "lambda: 1",
    "x[0]",
    "x; y",
    "getattr(x, 'n')",
    "x.subs",
]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_safe_parse_expr_refuses_non_math(payload):
    with pytest.raises(UnsafeExpression):
        safe_parse_expr(payload)


@pytest.mark.parametrize("text", ["exec(chr(112))", "len(x)", "eval(x)", "breakpoint()"])
def test_evaluation_has_no_python_builtins(text):
    # Layer 3: inside the alphabet, Python builtins are unreachable. These names come back
    # as inert SymPy objects (or SymPy fails to combine them); if a builtin ran, exec/eval
    # would execute and len would return an int
    try:
        result = safe_parse_expr(text)
    except (TypeError, SyntaxError):
        return
    assert not isinstance(result, (int, str)) and result is not None


@pytest.mark.parametrize("payload", [p for p in PAYLOADS if p != "x[0]"])
def test_payloads_are_never_solved(payload):
    assert parse_math(payload) is None
    _, result = run_solver(payload)
    assert result.get("ok", True) is False


def test_matrix_expressions_cannot_reach_attributes():
    res = solve_linear_algebra(r"\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}.__class__")
    assert res.get("ok") is False


def test_matrix_transpose_still_works():
    res = solve_linear_algebra(r"\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}^T")
    assert res.get("ok", True) and res["answer"].tolist() == [[1, 3], [2, 4]]


def test_solver_workers_get_no_secrets(monkeypatch):
    import solver_pool
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret")
    pool = solver_pool.SolverPool(size=1, timeout=10, queue_timeout=60)
    try:
        assert pool.wait_ready(60)
        assert pool.run(os.getenv, "GEMINI_API_KEY") == ""
    finally:
        pool.close()


def test_image_bombs_are_rejected_before_decoding(tmp_path):
    from ocr.preprocessing import MAX_PIXELS, load_image
    side = int(MAX_PIXELS ** 0.5) + 100
    path = tmp_path / "bomb.png"
    Image.new("1", (side, side)).save(path)  # small file, huge declared size
    with pytest.raises(ValueError):
        load_image(str(path))


def test_huge_pdf_pages_fit_the_pixel_budget(tmp_path):
    from pdf.parser import MAX_PAGE_PIXELS, render_pdf_pages
    doc = pymupdf.open()
    doc.new_page(width=14400, height=14400)  # 200 × 200 inches
    path = tmp_path / "big.pdf"
    doc.save(path)
    doc.close()
    page = next(render_pdf_pages(str(path)))
    assert page.width * page.height <= MAX_PAGE_PIXELS * 1.01


def test_uploaded_photos_are_not_kept(monkeypatch):
    from fastapi.testclient import TestClient

    import config
    import pipeline
    from main import app
    monkeypatch.setattr(pipeline, "extract_latex_from_image", lambda img: "x = 2")
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    before = set(os.listdir(config.UPLOAD_DIR))
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, format="PNG")
    r = TestClient(app).post("/api/upload", files={"file": ("foto.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200 and r.json()["solved"]
    assert set(os.listdir(config.UPLOAD_DIR)) == before


def test_rate_limiter_memory_stays_bounded():
    """Many distinct IPs over time: idle keys are forgotten, so memory does not grow forever."""
    import time

    from ratelimit import RateLimiter
    limiter = RateLimiter(limit=5, window_seconds=0.01)
    for wave in range(4):
        for i in range(6_000):
            limiter.allow(f"ip-{wave}-{i}")
        time.sleep(0.05)  # the whole wave goes idle
    assert len(limiter._hits) <= 12_000  # 24 000 keys seen, at most the latest ones kept


def test_one_exercise_in_progress_per_user():
    from fastapi import HTTPException

    import models
    from api.router import _one_at_a_time
    user = models.User(id="impatient")
    with _one_at_a_time(user):
        with pytest.raises(HTTPException) as busy:
            with _one_at_a_time(user):
                pass
        assert busy.value.status_code == 429
    with _one_at_a_time(user):  # released afterwards
        pass
