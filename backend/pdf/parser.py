import pymupdf
from PIL import Image

MAX_PAGES = 5


def render_pdf_pages(pdf_path: str, max_pages: int = MAX_PAGES, dpi: int = 200):
    """
    Yield the first `max_pages` pages of a PDF as PIL images, rendered in memory
    (no temporary files). Lazy, so OCR can stop at the first page with math on it.
    """
    with pymupdf.open(pdf_path) as doc:
        for page_num in range(min(len(doc), max_pages)):
            pix = doc.load_page(page_num).get_pixmap(dpi=dpi)
            yield Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
