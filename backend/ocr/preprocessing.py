import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_SIDE = 2000


def load_image(image_path: str) -> Image.Image:
    """Open an image respecting EXIF rotation (phone photos) and cap its size."""
    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as e:
        raise ValueError(f"No se pudo abrir la imagen: {e}") from e
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img


def preprocess_for_local_ocr(image: Image.Image) -> Image.Image:
    """
    Noise reduction, grayscale and adaptive thresholding for the local pix2tex model.
    Vision LLMs (Gemini) get the original image: binarization removes information they use.
    """
    gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return Image.fromarray(thresh)
