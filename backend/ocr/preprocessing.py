import cv2
import numpy as np
from PIL import Image

def preprocess_image_for_ocr(image_path: str) -> Image.Image:
    """
    Applies noise reduction, grayscale conversion, and adaptive thresholding
    to prepare the mathematical expression image for the Pix2Tex OCR engine.
    """
    # Read image using OpenCV
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        # Fallback to PIL if OpenCV fails to read (e.g., unsupported format)
        try:
            return Image.open(image_path).convert("L")
        except Exception as e:
            raise ValueError(f"Could not read image from {image_path}: {e}")

    # Remove noise
    img_blurred = cv2.GaussianBlur(img, (5, 5), 0)

    # Adaptive Thresholding for better contrast
    img_thresh = cv2.adaptiveThreshold(
        img_blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    # Convert back to PIL Image as pix2tex expects PIL Images
    pil_image = Image.fromarray(img_thresh)
    return pil_image
