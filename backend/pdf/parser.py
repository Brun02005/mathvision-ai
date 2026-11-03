import math

import pymupdf
from PIL import Image

MAX_PAGES = 5
# Page size is chosen by whoever made the PDF: a 200-inch page at 200 dpi would be
# 40000×40000 px (4.8 GB). The zoom is lowered so every page fits this pixel budget.
MAX_PAGE_PIXELS = 8_000_000


def _zoom_for(page, dpi: int) -> float:
    width_pt, height_pt = page.rect.width, page.rect.height
    zoom = dpi / 72
    pixels = width_pt * zoom * height_pt * zoom
    if pixels > MAX_PAGE_PIXELS:
        zoom *= math.sqrt(MAX_PAGE_PIXELS / pixels)
    return zoom


def render_pdf_pages(pdf_path: str, max_pages: int = MAX_PAGES, dpi: int = 200):
    """
    Yield the first `max_pages` pages of a PDF as PIL images, rendered in memory
    (no temporary files), each within the pixel budget. Lazy, so OCR can stop at
    the first page with math on it.
    """
    with pymupdf.open(pdf_path) as doc:
        for page_num in range(min(len(doc), max_pages)):
            page = doc.load_page(page_num)
            zoom = _zoom_for(page, dpi)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
            yield Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
