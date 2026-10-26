import io
import os

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import config
import pipeline
from main import app

client = TestClient(app)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, format="PNG")
    return buf.getvalue()


def _pdf_bytes() -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "x^2 = 4")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def fake_ocr(monkeypatch):
    """Replace the OCR provider so tests do not need Gemini or pix2tex."""
    def set_result(latex):
        monkeypatch.setattr(pipeline, "extract_latex_from_image", lambda img: latex)
    return set_result


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to MathVision AI API"}


def test_health_reports_ocr_providers():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert set(body["ocr"]) == {"gemini", "pix2tex"}


def test_solve_text_teacher_mode():
    r = client.post("/api/solve-text", data={"latex_expression": "x^2 - 4 = 0", "mode": "Teacher"})
    assert r.status_code == 200
    body = r.json()
    assert body["final_result_latex"] == r"x \in \left\{-2,\; 2\right\}"
    assert body["steps"] and body["id"] is not None
    assert body["graph_data"]["data"]


def test_exam_mode_hides_steps_but_history_keeps_them():
    r = client.post("/api/solve-text", data={"latex_expression": r"\int x dx", "mode": "Exam"})
    body = r.json()
    assert body["steps"] == []
    detail = client.get(f"/api/history/{body['id']}").json()
    assert detail["steps"]


def test_invalid_mode_rejected():
    r = client.post("/api/solve-text", data={"latex_expression": "1+1", "mode": "Hack"})
    assert r.status_code == 422


def test_empty_expression_is_422():
    r = client.post("/api/solve-text", data={"latex_expression": "   "})
    assert r.status_code == 422


def test_unsolvable_expression_is_not_saved():
    before = client.get("/api/history").json()["total"]
    r = client.post("/api/solve-text", data={"latex_expression": r"\frac{{"})
    assert r.status_code == 200 and r.json()["solved"] is False
    assert client.get("/api/history").json()["total"] == before


def test_history_crud_and_search():
    created = client.post("/api/solve-text", data={"latex_expression": r"\sum_{k=1}^{10} k"}).json()
    page = client.get("/api/history", params={"q": "Series"}).json()
    assert any(item["id"] == created["id"] for item in page["items"])

    assert client.get(f"/api/history/{created['id']}").status_code == 200
    assert client.delete(f"/api/history/{created['id']}").status_code == 204
    assert client.get(f"/api/history/{created['id']}").status_code == 404


def test_history_limit_is_bounded():
    assert client.get("/api/history", params={"limit": 10_000}).status_code == 422


def test_upload_image(fake_ocr):
    fake_ocr(r"\int_{0}^{1} x dx")
    r = client.post("/api/upload", files={"file": ("ejercicio.png", _png_bytes(), "image/png")},
                    data={"mode": "Teacher"})
    assert r.status_code == 200
    assert r.json()["final_result_latex"] == r"\frac{1}{2}"


def test_upload_pdf(fake_ocr):
    fake_ocr("x^2 = 4")
    r = client.post("/api/upload", files={"file": ("parcial.pdf", _pdf_bytes(), "application/pdf")})
    assert r.status_code == 200
    assert r.json()["final_result_latex"] == r"x \in \left\{-2,\; 2\right\}"


def test_upload_uses_random_filename(fake_ocr):
    fake_ocr("2 + 2")
    r = client.post("/api/upload", files={"file": ("../../evil.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    saved = os.listdir(config.UPLOAD_DIR)
    assert all("evil" not in name for name in saved)


def test_upload_without_math_is_422(fake_ocr):
    fake_ocr("")
    r = client.post("/api/upload", files={"file": ("blank.png", _png_bytes(), "image/png")})
    assert r.status_code == 422


def test_upload_rejects_other_formats():
    r = client.post("/api/upload", files={"file": ("script.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415


def test_upload_rejects_large_files(monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0)
    r = client.post("/api/upload", files={"file": ("big.png", _png_bytes(), "image/png")})
    assert r.status_code == 413


def test_clear_history():
    client.post("/api/solve-text", data={"latex_expression": "1 + 1"})
    assert client.delete("/api/history").status_code == 204
    assert client.get("/api/history").json()["total"] == 0
