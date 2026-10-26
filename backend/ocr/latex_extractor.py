"""
LaTeX OCR extractor.

Primary:  Google Gemini Vision (google-genai SDK). Model configurable with
          GEMINI_MODEL; the default alias always points to the current Flash model.
Fallback: pix2tex local model (optional, downloads ~400MB from HuggingFace on first use).
"""
import io
import logging
import os
import re

from PIL import Image

from ocr.preprocessing import preprocess_for_local_ocr

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-flash-latest"

PROMPT = r"""You are an OCR engine for university math and physics exercises.
Transcribe the (first) exercise in the image as a single line of LaTeX, using
exactly these conventions so a symbolic solver can parse it:
- Integrals: \int_{a}^{b} f(x)\,dx   Derivatives: \frac{d}{dx}(f(x))   Limits: \lim_{x \to a} f(x)
- Series: \sum_{n=1}^{\infty} a_n    Matrices: \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}
- Systems of equations: separate equations with ';'  e.g. 2x + y = 5; x - y = 1
- Differential equations: y' = 2y, y(0) = 1   (initial conditions after commas)
- Word problems (physics): the formula followed by the data, e.g. F = m a, m = 10 \text{kg}, a = 5 \text{m/s^2}
Return ONLY the LaTeX: no explanation, no markdown, no backticks, no $ delimiters.
If there is no math in the image, return an empty string."""


def _clean_response(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"^```(?:latex|tex)?\s*|\s*```$", "", s)
    s = s.strip().strip("$").strip()
    s = re.sub(r"^\\\[|\\\]$", "", s).strip()
    return s


# ── Gemini Vision OCR ──────────────────────────────────────────────────────────

_gemini_client = None


def gemini_available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _gemini_client


def _extract_with_gemini(image: Image.Image) -> str:
    if not gemini_available():
        return ""
    try:
        from google.genai import types

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        response = _get_gemini_client().models.generate_content(
            model=os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            contents=[types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png"), PROMPT],
            config=types.GenerateContentConfig(temperature=0),
        )
        latex = _clean_response(response.text)
        logger.info(f"Gemini OCR result: {latex}")
        return latex
    except Exception as e:
        logger.warning(f"Gemini OCR failed: {e}")
        return ""


# ── pix2tex local OCR ──────────────────────────────────────────────────────────

_pix2tex_model = None
_pix2tex_failed = False


def pix2tex_available() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("pix2tex") is not None
    except Exception:
        return False


def _get_pix2tex():
    global _pix2tex_model, _pix2tex_failed
    if _pix2tex_model is None and not _pix2tex_failed:
        try:
            from pix2tex.cli import LatexOCR
            logger.info("Loading pix2tex model (first time may take 1-2 min)…")
            _pix2tex_model = LatexOCR()
        except Exception as e:
            _pix2tex_failed = True
            logger.error(f"pix2tex load failed: {e}")
    return _pix2tex_model


def _extract_with_pix2tex(image: Image.Image) -> str:
    if not pix2tex_available():
        return ""
    model = _get_pix2tex()
    if model is None:
        return ""
    try:
        result = model(preprocess_for_local_ocr(image))
        logger.info(f"pix2tex result: {result}")
        return _clean_response(result)
    except Exception as e:
        logger.error(f"pix2tex inference failed: {e}")
        return ""


# ── Public API ─────────────────────────────────────────────────────────────────

def ocr_status() -> dict:
    return {"gemini": gemini_available(), "pix2tex": pix2tex_available()}


def extract_latex_from_image(image: Image.Image) -> str:
    """Try Gemini first, then pix2tex; empty string if neither finds math."""
    return _extract_with_gemini(image) or _extract_with_pix2tex(image)
