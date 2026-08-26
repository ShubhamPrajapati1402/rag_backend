import os
import tempfile
import time
from loguru import logger
from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title
from pypdf import PdfReader, PdfWriter
from app.services.classifier import classify_pdf_pages

def extract_raw_elements(file_path: str, strategy: str = "hi_res", fallback_pages: list = None):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF not found at: {file_path}")
        
    if strategy in ["hi_res", "fast"]:
        logger.info(f"Starting to parse PDF: {file_path} with strategy={strategy}")
        elements = partition_pdf(
            filename=file_path,
            strategy=strategy,
            multiprocessing=True,
        )
        logger.info(f"Successfully extracted {len(elements)} raw elements from PDF.")
        return elements
        
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
        
        print("--------------------------------------------------")
        print("PAGE ROUTING")
        print("--------------------------------------------------")
        fast_list = [str(c.page_number) for c in classifications if c.strategy == "fast"]
        hi_res_list = [f"{c.page_number} ({c.reason})" for c in classifications if c.strategy == "hi_res"]
        
        print(f"FAST:\n{', '.join(fast_list)}\n")
        print(f"HI_RES:\n{', '.join(hi_res_list)}\n")
        
        reader = PdfReader(file_path)
        all_elements = []
        
        fast_completed = 0
        hi_res_completed = 0
        
        with tempfile.TemporaryDirectory() as temp_dir:
            for i, page in enumerate(reader.pages):
                page_num = i + 1
                c = classifications[i]
                
                # Extract single page
                writer = PdfWriter()
                writer.add_page(page)
                page_path = os.path.join(temp_dir, f"page_{page_num}.pdf")
                with open(page_path, "wb") as f:
                    writer.write(f)
                    
                # Process with Unstructured
                elements = partition_pdf(
                    filename=page_path,
                    strategy=c.strategy,
                    multiprocessing=False
                )
                
                # Correct page number
                for el in elements:
                    if hasattr(el, 'metadata'):
                        el.metadata.page_number = page_num
                        
                all_elements.extend(elements)
                
                if c.strategy == "fast":
                    fast_completed += 1
                else:
                    hi_res_completed += 1
                    
        print("--------------------------------------------------")
        print("EXTRACTION")
        print("--------------------------------------------------")
        print(f"FAST pages completed  : {fast_completed}")
        print(f"HI_RES pages completed: {hi_res_completed}")
        
        total_chars = sum(len(el.text) for el in all_elements if hasattr(el, 'text') and el.text)
        print(f"\nTotal elements: {len(all_elements)}")
        print(f"Total characters: {total_chars}\n")
        
        return all_elements
        
    elif strategy == "hi_res_fallback" and fallback_pages:
        logger.info(f"Starting HI_RES fallback extraction for pages: {fallback_pages}")
        reader = PdfReader(file_path)
        fallback_elements = []
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
                
                elements = partition_pdf(
                    filename=page_path,
                    strategy="hi_res",
                    multiprocessing=False
                )
                for el in elements:
                    if hasattr(el, 'metadata'):
                        el.metadata.page_number = page_num
                fallback_elements.extend(elements)
        return fallback_elements
        
    else:
        raise ValueError(f"Unknown strategy or missing parameters: {strategy}")

def create_chunks(elements):
    chunks = chunk_by_title(
        elements,
        max_characters=1500,
        new_after_n_chars=1000,
        overlap=200
    )
    
    logger.info(f"Successfully grouped document into {len(chunks)} logical chunks.")
    
    formatted_chunks = []
    for i, chunk in enumerate(chunks):
        metadata = chunk.metadata.to_dict()
        formatted_chunks.append({
            "chunk_index": i,
            "text_content": chunk.text,
            "page_number": metadata.get("page_number", None),
            "metadata_json": metadata
        })
        
    return formatted_chunks

def process_pdf(file_path: str, strategy: str = "hi_res"):
    """
    Backward-compatible wrapper for normal ingestion.
    """
    elements = extract_raw_elements(file_path, strategy=strategy)
    return create_chunks(elements)
