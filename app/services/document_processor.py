import os
from loguru import logger
from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title

def extract_raw_elements(file_path: str, strategy: str = "hi_res"):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF not found at: {file_path}")
        
    logger.info(f"Starting to parse PDF: {file_path}")
    logger.info("This may take a moment as it analyzes the layout and tables...")
    
    elements = partition_pdf(
        filename=file_path,
        strategy=strategy,
        multiprocessing=True,
    )
    
    logger.info(f"Successfully extracted {len(elements)} raw elements from PDF.")
    return elements

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

def process_pdf(file_path: str):
    """
    Backward-compatible wrapper for normal ingestion.
    """
    elements = extract_raw_elements(file_path)
    return create_chunks(elements)
