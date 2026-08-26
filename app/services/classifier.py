import pdfplumber
import time
from typing import List, Dict, Any
from loguru import logger

class PageClassification:
    def __init__(self, page_number: int, strategy: str, reason: str):
        self.page_number = page_number
        self.strategy = strategy
        self.reason = reason

def classify_pdf_pages(file_path: str) -> List[PageClassification]:
    """
    Analyzes each page of a PDF using pdfplumber to determine whether it can be parsed
    safely with "fast" or if it requires "hi_res" (e.g. contains tables or is scanned).
    """
    logger.info(f"Starting page classification for {file_path} using pdfplumber...")
    start_time = time.time()
    classifications = []
    
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_number = i + 1
            
            # Detect tables based on lines/rectangles forming grids
            tables = page.find_tables()
            
            if len(tables) > 0:
                classifications.append(PageClassification(
                    page_number=page_number,
                    strategy="hi_res",
                    reason="table_detected"
                ))
                continue
            
            # Extract text to check for scanned pages
            text = page.extract_text()
            if not text or len(text.strip()) < 50:
                # If there's barely any text, it might be a scanned image or purely visual page
                classifications.append(PageClassification(
                    page_number=page_number,
                    strategy="hi_res",
                    reason="no_text"
                ))
                continue
                
            # Check for excessive visual complexity (many images/drawings but no explicit table)
            if len(page.images) > 3 or len(page.rects) > 50:
                classifications.append(PageClassification(
                    page_number=page_number,
                    strategy="hi_res",
                    reason="complex_layout"
                ))
                continue
                
            # Safe for fast extraction
            classifications.append(PageClassification(
                page_number=page_number,
                strategy="fast",
                reason="simple_text"
            ))
            
    duration = time.time() - start_time
    logger.info(f"Classification completed in {duration:.2f}s")
    
    return classifications
