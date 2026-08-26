import os
import sys
import time
import random
import hashlib
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from loguru import logger
from urllib3.exceptions import HTTPError as URLLib3HTTPError

# Required so Python can find the 'app' module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.document_processor import process_pdf
from app.services.embeddings import get_embeddings_model
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update, or_, and_

def get_file_hash(file_path: str) -> str:
    """Calculates the SHA-256 hash of the actual file bytes."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_config_hash() -> str:
    """Calculates a deterministic hash of the ingestion configuration."""
    config_dict = {
        "model": settings.HUGGINGFACE_EMBEDDING_MODEL,
        # Add chunking parameters here if they become configurable
    }
    config_str = json.dumps(config_dict, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()

def embed_with_retry(embeddings_model, texts, max_retries=3):
    """Wraps the embedding call with exponential backoff for transient HF errors."""
    for attempt in range(max_retries):
        try:
            return embeddings_model.embed_documents(texts)
        except Exception as e:
            is_transient = False
            status_code = getattr(getattr(e, 'response', None), 'status_code', None)
            
            if status_code:
                if status_code in (429, 500, 502, 503, 504):
                    is_transient = True
            else:
                if isinstance(e, (requests.exceptions.RequestException, URLLib3HTTPError, TimeoutError, ConnectionError)):
                    is_transient = True

            if not is_transient:
                logger.error(f"Permanent API error ({status_code}): {type(e).__name__} - {e}")
                raise e
            
            if attempt == max_retries - 1:
                logger.error(f"Max retries ({max_retries}) reached. Transient error persists: {e}")
                raise e
                
            sleep_time = (2 ** attempt) + random.uniform(0, 1)
            logger.warning(f"Transient API error (status={status_code}). Retrying in {sleep_time:.2f}s... (Attempt {attempt+1}/{max_retries})")
            time.sleep(sleep_time)

def process_embedding_batch(batch_idx: int, chunks_batch: list, embeddings_model) -> tuple:
    """Worker function: ONLY calls the Hugging Face API."""
    preview = chunks_batch[0]["text_content"][:40].replace('\n', ' ')
    logger.info(f"[Batch {batch_idx+1}] Started | Preview: '{preview}...'")
    
    start_time = time.time()
    try:
        texts_to_embed = [chunk["text_content"] for chunk in chunks_batch]
        embeddings = embed_with_retry(embeddings_model, texts_to_embed, max_retries=3)
        req_time = time.time() - start_time
        return batch_idx, chunks_batch, embeddings, req_time, None
    except Exception as e:
        return batch_idx, chunks_batch, None, 0.0, e

def persist_batch(document_id: int, chunks_batch: list, embeddings: list):
    """Persistence stage: Atomically commits a batch and renews the lease."""
    db = SessionLocal()
    try:
        db_records = []
        for chunk, embedding in zip(chunks_batch, embeddings):
            db_record = DocumentChunk(
                document_id=document_id,
                page_number=chunk["page_number"],
                chunk_index=chunk["chunk_index"],
                text_content=chunk["text_content"],
                metadata_json=chunk["metadata_json"],
                embedding=embedding
            )
            db_records.append(db_record)
            
        db.add_all(db_records)
        
        # Renew the lease in the exact same transaction
        db.query(Document).filter(Document.id == document_id).update({
            Document.updated_at: datetime.now(ZoneInfo("Asia/Kolkata"))
        })
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def ingest_pdf(file_path: str):
    logger.info(f"Starting ingestion process for: {file_path}")
    
    file_hash = get_file_hash(file_path)
    config_hash = get_config_hash()
    logger.info(f"File SHA-256 Hash: {file_hash}")
    logger.info(f"Config Hash: {config_hash}")
    
    db = SessionLocal()
    try:
        # 1. Attempt to insert as NEW if it doesn't exist
        document = db.query(Document).filter(Document.file_hash == file_hash).first()
        if not document:
            try:
                new_doc = Document(
                    filename=os.path.basename(file_path),
                    file_hash=file_hash,
                    config_hash=config_hash,
                    status=DocumentStatus.NEW
                )
                db.add(new_doc)
                db.commit()
            except IntegrityError:
                db.rollback() # It already exists, perfectly safe
        else:
            if document.status == DocumentStatus.COMPLETED:
                logger.info("Document already perfectly ingested (COMPLETED). Aborting.")
                return
                
            # STRICT REQUIREMENT: Never mix configurations!
            if document.config_hash != config_hash:
                logger.error(f"Configuration drift detected! Stored config_hash does not match current config_hash. Aborting to prevent mixed embeddings.")
                return
            
        # 2. Atomic Lease Acquisition
        lease_minutes = getattr(settings, "DOCUMENT_LEASE_MINUTES", 30)
        lease_expiry_threshold = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(minutes=lease_minutes)
        
        stmt = (
            update(Document)
            .where(Document.file_hash == file_hash)
            .where(
                or_(
                    Document.status == DocumentStatus.NEW,
                    Document.status == DocumentStatus.FAILED,
                    and_(
                        Document.status == DocumentStatus.PROCESSING,
                        Document.updated_at < lease_expiry_threshold
                    )
                )
            )
            .values(
                status=DocumentStatus.PROCESSING,
                updated_at=datetime.now(ZoneInfo("Asia/Kolkata"))
            )
            .returning(Document.id, Document.status)
        )
        
        result = db.execute(stmt).first()
        db.commit()
        
        if not result:
            # We failed to acquire the lease. Let's find out why.
            existing_doc = db.query(Document).filter(Document.file_hash == file_hash).first()
            if not existing_doc:
                logger.error("Catastrophic error: Document vanished during lease acquisition.")
                return
                
            if existing_doc.status == DocumentStatus.COMPLETED:
                logger.info("Document already perfectly ingested (COMPLETED). Aborting.")
            else:
                logger.error(f"Document is actively PROCESSING (lease acquired by another worker at {existing_doc.updated_at}). Aborting.")
            return

        document_id = result.id
        logger.info(f"Lease acquired for Document ID {document_id}.")
        
        # 3. Find perfectly persisted chunks to skip them
        existing_chunks = db.query(DocumentChunk.chunk_index).filter(DocumentChunk.document_id == document_id).all()
        persisted_indices = {c[0] for c in existing_chunks}
    finally:
        db.close()
        
    logger.info(f"Found {len(persisted_indices)} chunks already persisted for this document.")
    
    # 4. Parse and chunk the PDF
    try:
        all_chunks = process_pdf(file_path)
    except Exception as e:
        logger.error(f"Failed to process PDF: {e}")
        db = SessionLocal()
        db.query(Document).filter(Document.id == document_id).update({Document.status: DocumentStatus.FAILED})
        db.commit()
        db.close()
        return
        
    if not all_chunks:
        logger.warning("No chunks were extracted. Aborting ingestion.")
        db = SessionLocal()
        db.query(Document).filter(Document.id == document_id).update({Document.status: DocumentStatus.FAILED})
        db.commit()
        db.close()
        return

    # Filter out chunks that are already in the database
    chunks_to_process = [c for c in all_chunks if c["chunk_index"] not in persisted_indices]
    
    if not chunks_to_process:
        logger.info("All chunks are already securely embedded in the database. Marking as COMPLETED.")
        db = SessionLocal()
        db.query(Document).filter(Document.id == document_id).update({"status": DocumentStatus.COMPLETED})
        db.commit()
        db.close()
        return
        
    logger.info(f"{len(chunks_to_process)} remaining chunks need to be embedded.")

    # 5. Initialize the embeddings model
    ingest_start_time = time.time()
    logger.info("Initializing Hugging Face embeddings model...")
    embeddings_model = get_embeddings_model()
    
    # 6. Generate embeddings and save to database incrementally
    batch_size = 32
    max_workers = getattr(settings, "EMBEDDING_MAX_WORKERS", 5)
    
    batches = [chunks_to_process[i:i + batch_size] for i in range(0, len(chunks_to_process), batch_size)]
    logger.info(f"Splitting {len(chunks_to_process)} chunks into {len(batches)} batches of {batch_size}. Max workers: {max_workers}")
    
    batch_iterator = iter(enumerate(batches))
    active_futures = set()
    
    total_embedded_chunks = 0
    total_aggregate_worker_time = 0.0
    failed_batches = 0
    success_batches = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Bounded Backpressure: Submit initial batches up to max_workers
        for _ in range(max_workers):
            try:
                batch_idx, batch = next(batch_iterator)
                active_futures.add(executor.submit(process_embedding_batch, batch_idx, batch, embeddings_model))
            except StopIteration:
                break
                
        while active_futures:
            # Wait for at least one batch to complete
            done, active_futures = wait(active_futures, return_when=FIRST_COMPLETED)
            
            for future in done:
                batch_idx, chunks_batch, embeddings, req_time, error = future.result()
                
                if error:
                    failed_batches += 1
                    logger.error(f"[Batch {batch_idx+1}] Permanent failure! Error: {error}")
                else:
                    try:
                        # Dedicated Persistence Stage
                        persist_batch(document_id, chunks_batch, embeddings)
                        success_batches += 1
                        total_embedded_chunks += len(chunks_batch)
                        total_aggregate_worker_time += req_time
                        logger.info(f"[Batch {batch_idx+1}] Successfully persisted to Postgres.")
                    except Exception as db_err:
                        failed_batches += 1
                        logger.error(f"[Batch {batch_idx+1}] Database persistence failed: {db_err}")
                
                # Bounded Backpressure: Submit next batch ONLY if we haven't failed
                if failed_batches == 0:
                    try:
                        next_idx, next_batch = next(batch_iterator)
                        active_futures.add(executor.submit(process_embedding_batch, next_idx, next_batch, embeddings_model))
                    except StopIteration:
                        pass
            
            # Fail-fast: Cancel unstarted futures and drain
            if failed_batches > 0:
                logger.warning("A batch failed! Canceling unstarted queued tasks (running API requests may finish)...")
                for f in active_futures:
                    f.cancel()
                break

    # Telemetry
    total_wall_clock_time = time.time() - ingest_start_time
    chunks_per_sec = total_embedded_chunks / total_wall_clock_time if total_wall_clock_time > 0 else 0
    req_per_sec = success_batches / total_wall_clock_time if total_wall_clock_time > 0 else 0
    
    logger.info(f"📊 --- API TELEMETRY ---")
    logger.info(f"📊 Total Chunks: {len(chunks_to_process)} | Total Batches: {len(batches)}")
    logger.info(f"📊 Batch Size: {batch_size} | Max Workers: {max_workers}")
    logger.info(f"📊 Successful Batches: {success_batches} | Failed Batches: {failed_batches}")
    logger.info(f"📊 Wall-Clock API Time: {total_wall_clock_time:.2f}s | (Aggregate Worker Time: {total_aggregate_worker_time:.2f}s)")
    logger.info(f"📊 Speed: {chunks_per_sec:.2f} chunks/sec | {req_per_sec:.2f} requests/sec")
    logger.info(f"📊 -----------------------")
    
    # Update Document Status
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if failed_batches > 0:
            doc.status = DocumentStatus.FAILED
            logger.error("Ingestion marked as FAILED due to batch errors. Fix the issue and run again to resume.")
        else:
            doc.status = DocumentStatus.COMPLETED
            logger.info("✅ Ingestion fully COMPLETED!")
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    target_pdf = os.path.join(os.getcwd(), "data", "uploads", "World Bank Group Annual Report 2025.pdf")
    ingest_pdf(target_pdf)
