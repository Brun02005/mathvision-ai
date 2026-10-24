"""
LaTeX OCR extractor.

Primary:  Google Gemini Vision API (fast, no local model download required)
Fallback: pix2tex local model (slow first load — downloads ~400MB from HuggingFace)
"""

import logging
import base64
import os
from PIL import Image
import io

logger = logging.getLogger(__name__)

# ── Gemini Vision OCR ──────────────────────────────────────────────────────────

def _extract_with_gemini(image: Image.Image) -> str:
    """
    Send the image to Gemini Vision and ask it to return the LaTeX expression.
    Requires GEMINI_API_KEY env variable OR google-generativeai installed.
    """
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Convert PIL image to bytes
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        prompt = (
            "Extract the mathematical expression from this image and return it "
            "as a LaTeX string ONLY. Do not add any explanation, markdown, or "
            "backticks. Return only the raw LaTeX. Examples of valid outputs: "
            r"\int_{0}^{\pi} \sin(x)\,dx  or  x^2 - 4 = 0"
        )

        response = model.generate_content([
            prompt,
            {"mime_type": "image/png", "data": base64.b64encode(image_bytes).decode()}
        ])
        latex = response.text.strip().strip("`").strip()
        logger.info(f"Gemini OCR result: {latex}")
        return latex

    except Exception as e:
        logger.warning(f"Gemini OCR failed: {e}")
        return ""


# ── pix2tex local OCR ──────────────────────────────────────────────────────────

_pix2tex_model = None

def _get_pix2tex():
    global _pix2tex_model
    if _pix2tex_model is None:
        try:
            from pix2tex.cli import LatexOCR
            logger.info("Loading pix2tex model (first time may take 1-2 min)…")
            _pix2tex_model = LatexOCR()
        except Exception as e:
            logger.error(f"pix2tex load failed: {e}")
    return _pix2tex_model


def _extract_with_pix2tex(image: Image.Image) -> str:
    model = _get_pix2tex()
    if model is None:
        return ""
    try:
        result = model(image)
        logger.info(f"pix2tex result: {result}")
        return result or ""
    except Exception as e:
        logger.error(f"pix2tex inference failed: {e}")
        return ""


# ── Public API ─────────────────────────────────────────────────────────────────

def extract_latex_from_image(image: Image.Image) -> str:
    """
    Try Gemini first (fast), then pix2tex (local), then return empty string.
    """
    # 1. Gemini Vision
    result = _extract_with_gemini(image)
    if result:
        return result

    # 2. pix2tex local model
    result = _extract_with_pix2tex(image)
    if result:
        return result

    return ""
