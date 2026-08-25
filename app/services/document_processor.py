import os
from loguru import logger
from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title

def process_pdf(file_path: str):
    """
    Uses the Unstructured library to parse a PDF, extracting text and tables,
    and then chunks it intelligently based on the document's structure (titles, sections).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF not found at: {file_path}")
        
    logger.info(f"Starting to parse PDF: {file_path}")
    logger.info("This may take a moment as it analyzes the layout and tables...")
    
    # Partition the PDF (this reads the structure, paragraphs, and tables)
    # Using hi_res for maximum accuracy with tables, and multiprocessing to split the pages across your CPU cores!
    elements = partition_pdf(
        filename=file_path,
        strategy="hi_res",
        multiprocessing=True,
    )
    
    logger.info(f"Successfully extracted {len(elements)} raw elements from PDF.")
    
    # Chunk the elements by title (this groups paragraphs under their respective headers)
    chunks = chunk_by_title(
        elements,
        max_characters=1500,     # Max size of a chunk
        new_after_n_chars=1000,  # Try to break if it gets larger than this
        overlap=200              # Overlap slightly so context isn't lost between chunks
    )
    
    logger.info(f"Successfully grouped document into {len(chunks)} logical chunks.")
    
    # Format chunks into a clean dictionary so we can easily save them to our database later
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
