import fitz  # PyMuPDF
import os

def extract_images_from_pdf(pdf_path: str, output_dir: str = "temp/pdf_images") -> list:
    """
    Extracts all pages as high-resolution images from a PDF file to be processed by OCR.
    Returns a list of image file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    image_paths = []
    
    # Iterate through all pages and render them as images
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        
        # Render the page at 300 DPI for better OCR accuracy
        pix = page.get_pixmap(dpi=300)
        img_path = os.path.join(output_dir, f"pdf_{os.path.basename(pdf_path)}_page_{page_num}.png")
        pix.save(img_path)
        image_paths.append(img_path)
        
    return image_paths
