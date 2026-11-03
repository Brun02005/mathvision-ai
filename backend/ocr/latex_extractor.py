"""
LaTeX OCR extractor.

Primary:  Google Gemini Vision (google-genai SDK). Model configurable with
          GEMINI_MODEL; the default alias always points to the current Flash model.
Fallback: pix2tex local model (optional, downloads ~400MB from HuggingFace on first use).

Two different outcomes are kept apart on purpose:
- ""                    a provider read the image and found no math (the user should retake the photo)
- OCRUnavailableError   no provider could read it at all (not configured, quota, network…)
"""
import io
import logging
import os
import re

from PIL import Image

from interpreter import metering
from ocr.preprocessing import preprocess_for_local_ocr

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
GEMINI_TIMEOUT_MS = 30_000

PROMPT = r"""You are an OCR engine for math and physics exercises (school or university,
printed or handwritten, possibly blurry or photographed at an angle).
If the (first) exercise is a word problem, transcribe its full statement as plain text
in its original language, keeping any formulas in LaTeX.
Otherwise transcribe it as a single line of LaTeX, using
exactly these conventions so a symbolic solver can parse it:
- Integrals: \int_{a}^{b} f(x)\,dx   Derivatives: \frac{d}{dx}(f(x))   Limits: \lim_{x \to a} f(x)
- Series: \sum_{n=1}^{\infty} a_n    Matrices: \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}
- Systems of equations: separate equations with ';'  e.g. 2x + y = 5; x - y = 1
- Differential equations: y' = 2y, y(0) = 1   (initial conditions after commas)
- Word problems (physics): the formula followed by the data, e.g. F = m a, m = 10 \text{kg}, a = 5 \text{m/s^2}
Return ONLY the transcription: no explanation, no markdown, no backticks, no $ delimiters
around a pure formula, and never solve the exercise.
If there is no math in the image, return an empty string."""


class OCRUnavailableError(RuntimeError):
    """No OCR provider could process the image."""


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
        from google.genai import types
        # Without a timeout a stalled connection would hold the request thread indefinitely
        _gemini_client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
        )
    return _gemini_client


def _extract_with_gemini(image: Image.Image) -> str:
    from google.genai import types

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    response = _get_gemini_client().models.generate_content(
        model=os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        contents=[types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png"), PROMPT],
        config=types.GenerateContentConfig(temperature=0),
    )
    metering.record(response, assistant=False)
    latex = _clean_response(response.text)
    logger.debug(f"Gemini OCR result: {latex}")
    return latex


# ── pix2tex local OCR ──────────────────────────────────────────────────────────

_pix2tex_model = None
_pix2tex_load_error = None


def pix2tex_available() -> bool:
    if _pix2tex_load_error is not None:
        return False
    try:
        import importlib.util
        return importlib.util.find_spec("pix2tex") is not None
    except Exception:
        return False


def _get_pix2tex():
    global _pix2tex_model, _pix2tex_load_error
    if _pix2tex_model is None:
        try:
            from pix2tex.cli import LatexOCR
            logger.info("Loading pix2tex model (first time may take 1-2 min)…")
            _pix2tex_model = LatexOCR()
        except Exception as e:
            # Loading takes minutes: don't retry it on every request
            _pix2tex_load_error = e
            raise
    return _pix2tex_model


def _extract_with_pix2tex(image: Image.Image) -> str:
    result = _get_pix2tex()(preprocess_for_local_ocr(image))
    logger.debug(f"pix2tex result: {result}")
    return _clean_response(result)


# ── Public API ─────────────────────────────────────────────────────────────────

_PROVIDERS = (
    ("Gemini", gemini_available, _extract_with_gemini),
    ("pix2tex", pix2tex_available, _extract_with_pix2tex),
)


def ocr_status() -> dict:
    return {"gemini": gemini_available(), "pix2tex": pix2tex_available()}


def extract_latex_from_image(image: Image.Image) -> str:
    """
    Try each configured provider in order. Returns the first LaTeX found, or ""
    if at least one provider read the image and found no math. Raises
    OCRUnavailableError when none is configured or all of them failed.
    """
    answered = False
    for name, available, extract in _PROVIDERS:
        if not available():
            continue
        try:
            latex = extract(image)
        except Exception as e:
            logger.warning(f"{name} OCR failed: {e}")
            continue
        answered = True
        if latex:
            return latex
    if not answered:
        raise OCRUnavailableError(
            "El servicio de lectura de imágenes no está disponible en este momento. "
            "Probá de nuevo en unos minutos o escribí el ejercicio en modo texto."
        )
    return ""
