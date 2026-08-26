import os
import sys
from loguru import logger

# Required so Python can find the 'app' module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db.session import SessionLocal
from app.models.document import DocumentChunk
from app.services.document_processor import process_pdf
from app.services.embeddings import get_embeddings_model

def ingest_pdf(file_path: str):
    logger.info(f"Starting ingestion process for: {file_path}")
    
    # 1. Parse and chunk the PDF
    try:
        chunks = process_pdf(file_path)
    except Exception as e:
        logger.error(f"Failed to process PDF: {e}")
        return
        
    if not chunks:
        logger.warning("No chunks were extracted. Aborting ingestion.")
        return

    # 2. Initialize the embeddings model
    logger.info("Initializing Hugging Face embeddings model (BAAI/bge-m3)...")
    embeddings_model = get_embeddings_model()
    
    # 3. Generate embeddings and save to database
    logger.info(f"Generating embeddings for {len(chunks)} chunks and saving to Supabase...")
    db = SessionLocal()
    
    try:
        # Extract just the raw text strings for the embedding model
        texts_to_embed = [chunk["text_content"] for chunk in chunks]
        
        # Preview the first chunk so the user can see what the text looks like!
        if texts_to_embed:
            logger.info("Here is a preview of the text from Chunk 1 before we turn it into math:")
            logger.info(f"\n{'-'*50}\n{texts_to_embed[0]}\n{'-'*50}\n")
        
        # Generate the math vectors via the Hugging Face API
        logger.info("Calling Hugging Face API... (This might take a minute depending on document size)")
        embeddings = embeddings_model.embed_documents(texts_to_embed)
        
        # Combine the chunks with their new embeddings and prepare them for the database
        db_records = []
        for chunk, embedding in zip(chunks, embeddings):
            db_record = DocumentChunk(
                source=os.path.basename(file_path),
                page_number=chunk["page_number"],
                chunk_index=chunk["chunk_index"],
                text_content=chunk["text_content"],
                metadata_json=chunk["metadata_json"],
                embedding=embedding
            )
            db_records.append(db_record)
            
        # Bulk save everything into Supabase
        db.add_all(db_records)
        db.commit()
        
        logger.info(f"✅ Successfully ingested {len(db_records)} chunks into Supabase!")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed during embedding or database insertion: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Look for the World Bank PDF in the data/uploads folder
    target_pdf = os.path.join(os.getcwd(), "data", "uploads", "World Bank Group Annual Report 2025.pdf")
    
    ingest_pdf(target_pdf)
