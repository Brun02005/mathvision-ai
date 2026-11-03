import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_SIDE = 2000
# Decompression bombs: a 10 MB PNG can declare 30000×30000 pixels (~2.7 GB once decoded).
# The size is in the header, so it is checked BEFORE decoding. 24 MP covers phone photos.
MAX_PIXELS = 24_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # Pillow's own guard, as a second barrier


def load_image(image_path: str) -> Image.Image:
    """Open an image respecting EXIF rotation (phone photos) and cap its size."""
    try:
        img = Image.open(image_path)  # lazy: reads only the header
        width, height = img.size
        if width * height > MAX_PIXELS:
            raise ValueError("too many pixels")
        # JPEG can decode directly at a reduced scale: never materialize the full photo
        img.draft("RGB", (MAX_SIDE, MAX_SIDE))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as e:
        # No library details for the user (they can reveal internals); the cause goes to the caller's log
        raise ValueError("No se pudo abrir la imagen. Probá con una foto JPG o PNG de menor resolución.") from e
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
