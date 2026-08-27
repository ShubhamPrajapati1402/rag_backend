import os
import tempfile
import time
from typing import List, Dict, Any
from loguru import logger
from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title
from pypdf import PdfReader, PdfWriter

from app.models.document_element import DocumentElement
from app.services.parsers.base import BaseParser
from app.services.classifier import classify_pdf_pages
from app.services.validator import PDFValidator

class PDFParser(BaseParser):
    """
    Parser for PDF files. Preserves the original production hybrid architecture.
    """
    def __init__(self, strategy: str = "hi_res", fallback_pages: list = None):
        self.strategy = strategy
        self.fallback_pages = fallback_pages
        self._cached_raw_elements = None # Store raw unstructured elements for chunking and validation

    def parse(self, file_path: str, **kwargs) -> List[DocumentElement]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF not found at: {file_path}")
            
        strategy = self.strategy
        fallback_pages = self.fallback_pages
        
        if strategy in ["hi_res", "fast"]:
            logger.info(f"Starting to parse PDF: {file_path} with strategy={strategy}")
            raw_elements = partition_pdf(
                filename=file_path,
                strategy=strategy,
                multiprocessing=True,
            )
            logger.info(f"Successfully extracted {len(raw_elements)} raw elements from PDF.")
            
        elif strategy == "hybrid":
            logger.info(f"Starting HYBRID extraction for {file_path}")
            class_start = time.time()
            classifications = classify_pdf_pages(file_path)
            
            fast_pages = sum(1 for c in classifications if c.strategy == "fast")
            hi_res_pages = sum(1 for c in classifications if c.strategy == "hi_res")
            
            print("\n==================================================")
            print("PDF HYBRID CLASSIFICATION")
            print("==================================================")
            print(f"Total pages : {len(classifications)}")
            print(f"FAST pages  : {fast_pages}")
            print(f"HI_RES pages: {hi_res_pages}")
            print("==================================================\n")
            
            fast_list = [str(c.page_number) for c in classifications if c.strategy == "fast"]
            hi_res_list = [f"{c.page_number} ({c.reason})" for c in classifications if c.strategy == "hi_res"]
            
            print("--------------------------------------------------")
            print("PAGE ROUTING")
            print("--------------------------------------------------")
            print(f"FAST:\n{', '.join(fast_list)}\n")
            print(f"HI_RES:\n{', '.join(hi_res_list)}\n")
            
            reader = PdfReader(file_path)
            raw_elements = []
            
            fast_completed = 0
            hi_res_completed = 0
            
            with tempfile.TemporaryDirectory() as temp_dir:
                for i, page in enumerate(reader.pages):
                    page_num = i + 1
                    c = classifications[i]
                    
                    writer = PdfWriter()
                    writer.add_page(page)
                    page_path = os.path.join(temp_dir, f"page_{page_num}.pdf")
                    with open(page_path, "wb") as f:
                        writer.write(f)
                        
                    page_elements = partition_pdf(
                        filename=page_path,
                        strategy=c.strategy,
                        multiprocessing=False
                    )
                    
                    for el in page_elements:
                        if hasattr(el, 'metadata'):
                            el.metadata.page_number = page_num
                            
                    raw_elements.extend(page_elements)
                    
                    if c.strategy == "fast":
                        fast_completed += 1
                    else:
                        hi_res_completed += 1
                        
            print("--------------------------------------------------")
            print("EXTRACTION")
            print("--------------------------------------------------")
            print(f"FAST pages completed  : {fast_completed}")
            print(f"HI_RES pages completed: {hi_res_completed}")
            
            total_chars = sum(len(el.text) for el in raw_elements if hasattr(el, 'text') and el.text)
            print(f"\nTotal elements: {len(raw_elements)}")
            print(f"Total characters: {total_chars}\n")
            
        elif strategy == "hi_res_fallback" and fallback_pages:
            logger.info(f"Starting HI_RES fallback extraction for pages: {fallback_pages}")
            reader = PdfReader(file_path)
            raw_elements = []
            with tempfile.TemporaryDirectory() as temp_dir:
                for page_num in fallback_pages:
                    idx = page_num - 1
                    if idx < 0 or idx >= len(reader.pages):
                        continue
                    page = reader.pages[idx]
                    writer = PdfWriter()
                    writer.add_page(page)
                    page_path = os.path.join(temp_dir, f"page_{page_num}.pdf")
                    with open(page_path, "wb") as f:
                        writer.write(f)
                    
                    page_elements = partition_pdf(
                        filename=page_path,
                        strategy="hi_res",
                        multiprocessing=False
                    )
                    for el in page_elements:
                        if hasattr(el, 'metadata'):
                            el.metadata.page_number = page_num
                    raw_elements.extend(page_elements)
        else:
            raise ValueError(f"Unknown strategy or missing parameters: {strategy}")

        self._cached_raw_elements = raw_elements

        # Convert to Unified DocumentElement
        doc_elements = []
        for el in raw_elements:
            el_type = type(el).__name__
            text = el.text if hasattr(el, 'text') else str(el)
            meta = el.metadata.to_dict() if hasattr(el, 'metadata') else {}
            meta['source_type'] = 'pdf'
            doc_elements.append(DocumentElement(element_type=el_type, content=text, metadata=meta))
            
        return doc_elements

    def chunk(self, elements: List[DocumentElement]) -> List[Dict[str, Any]]:
        if not self._cached_raw_elements:
            raise RuntimeError("PDF chunking requires _cached_raw_elements from parse(). Call parse() first.")
            
        chunks = chunk_by_title(
            self._cached_raw_elements,
            max_characters=1500,
            new_after_n_chars=1000,
            overlap=200
        )
        
        logger.info(f"Successfully grouped PDF into {len(chunks)} logical chunks.")
        
        formatted_chunks = []
        for i, chunk in enumerate(chunks):
            metadata = chunk.metadata.to_dict()
            metadata['source_type'] = 'pdf'
            formatted_chunks.append({
                "chunk_index": i,
                "text_content": chunk.text,
                "page_number": metadata.get("page_number", None),
                "metadata_json": metadata
            })
            
        return formatted_chunks
        
    def get_validator(self) -> PDFValidator:
        if not self._cached_raw_elements:
            raise RuntimeError("Cannot create PDFValidator without parsed elements.")
        return PDFValidator(self._cached_raw_elements)
