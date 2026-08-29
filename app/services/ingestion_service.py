import os
import io
import time
import json
import hashlib
from typing import AsyncGenerator, Dict, Any, List
from datetime import datetime
from zoneinfo import ZoneInfo
from loguru import logger
import pypdf

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.parsers.registry import ParserRegistry
import app.services.parsers # Ensure all parsers are registered
from app.services.embeddings import get_embeddings_model
from app.scripts.ingest import embed_with_retry, get_config_hash

def format_sse(event: str, data: dict) -> str:
    """Helper to format Server-Sent Event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

def get_page_count_safe(file_path: str, filename: str) -> int:
    """Detects total pages or structural units dynamically."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        try:
            reader = pypdf.PdfReader(file_path)
            return max(len(reader.pages), 1)
        except Exception:
            return 1
    return 1

async def stream_dynamic_ingestion(
    file_bytes: bytes,
    filename: str,
    user_id: int
) -> AsyncGenerator[str, None]:
    """
    Asynchronously executes multi-format parsing, chunking, embedding, and persistence
    while streaming real-time, dynamic layman progress updates via Server-Sent Events.
    """
    # 1. Save to temporary directory
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    temp_file_path = os.path.join(upload_dir, f"temp_{int(time.time())}_{filename}")

    with open(temp_file_path, "wb") as f:
        f.write(file_bytes)

    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    config_hash = get_config_hash()

    try:
        # Phase 1: File Analysis & Discovery (5%)
        total_pages = get_page_count_safe(temp_file_path, filename)
        yield format_sse("progress", {
            "percent": 5,
            "stage": "intake",
            "message": f"Analyzing '{filename}' ({total_pages} page{'s' if total_pages > 1 else ''} detected)..."
        })

        db = SessionLocal()
        try:
            # Check existing document or create new record
            doc = db.query(Document).filter(
                Document.user_id == user_id,
                Document.filename == filename
            ).first()

            if not doc:
                doc = Document(
                    user_id=user_id,
                    filename=filename,
                    file_hash=sha256_hash,
                    config_hash=config_hash,
                    status=DocumentStatus.PROCESSING
                )
                db.add(doc)
            else:
                doc.file_hash = sha256_hash
                doc.config_hash = config_hash
                doc.status = DocumentStatus.PROCESSING
                # Clear previous chunks if re-ingesting
                db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()

            db.commit()
            db.refresh(doc)
            document_id = doc.id
        finally:
            db.close()

        # Phase 2: Page-by-Page Extraction & Parsing (5% -> 45%)
        yield format_sse("progress", {
            "percent": 15,
            "stage": "parsing",
            "message": f"Reading and extracting structured content from {total_pages} page{'s' if total_pages > 1 else ''}..."
        })

        parser = ParserRegistry.get_parser(temp_file_path)
        elements = parser.parse(temp_file_path)

        yield format_sse("progress", {
            "percent": 45,
            "stage": "parsing_complete",
            "message": f"Extracted {len(elements)} structural elements with layout preservation."
        })

        # Phase 3: Semantic Partitioning (45% -> 55%)
        yield format_sse("progress", {
            "percent": 50,
            "stage": "chunking",
            "message": "Organizing text into smart, searchable topic sections..."
        })

        chunks = parser.chunk(elements)
        total_chunks = len(chunks)

        if total_chunks == 0:
            raise ValueError(f"No readable content could be extracted from '{filename}'.")

        yield format_sse("progress", {
            "percent": 55,
            "stage": "chunking_complete",
            "message": f"Created {total_chunks} smart sections ready for AI learning."
        })

        # Phase 4: Dynamic Batch Vector Embedding (55% -> 90%)
        embeddings_model = get_embeddings_model()
        batch_size = 16
        all_embeddings = []

        for i in range(0, total_chunks, batch_size):
            batch = chunks[i: i + batch_size]
            texts_to_embed = [chunk["text_content"] for chunk in batch]
            
            batch_vectors = embed_with_retry(embeddings_model, texts_to_embed, max_retries=3)
            all_embeddings.extend(batch_vectors)

            completed = min(i + batch_size, total_chunks)
            embed_pct = 55 + int((completed / total_chunks) * 35)

            yield format_sse("progress", {
                "percent": embed_pct,
                "stage": "embedding",
                "message": f"Teaching AI concepts ({completed} of {total_chunks} sections learned)...",
                "completed_chunks": completed,
                "total_chunks": total_chunks
            })

        # Phase 5: Persistence to PostgreSQL & pgvector (90% -> 100%)
        yield format_sse("progress", {
            "percent": 92,
            "stage": "persisting",
            "message": "Saving knowledge index to your secure workspace..."
        })

        db = SessionLocal()
        try:
            db_records = []
            for chunk, embedding in zip(chunks, all_embeddings):
                db_record = DocumentChunk(
                    document_id=document_id,
                    page_number=chunk.get("page_number"),
                    chunk_index=chunk.get("chunk_index", 0),
                    text_content=chunk["text_content"],
                    metadata_json=chunk.get("metadata_json", {}),
                    embedding=embedding
                )
                db_records.append(db_record)

            db.bulk_save_objects(db_records)

            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = DocumentStatus.COMPLETED
                doc.completed_at = datetime.now(ZoneInfo("Asia/Kolkata"))
            db.commit()
        finally:
            db.close()

        # Phase 6: Completed
        yield format_sse("done", {
            "percent": 100,
            "document_id": document_id,
            "filename": filename,
            "total_pages": total_pages,
            "total_chunks": total_chunks,
            "status": "completed",
            "message": f"Ready to chat! '{filename}' is fully learned ({total_chunks} sections indexed)."
        })

    except Exception as e:
        logger.error(f"[IngestStream] Dynamic ingestion error for '{filename}': {e}")
        db = SessionLocal()
        try:
            doc = db.query(Document).filter(
                Document.user_id == user_id,
                Document.filename == filename
            ).first()
            if doc:
                doc.status = DocumentStatus.FAILED
                db.commit()
        finally:
            db.close()

        yield format_sse("error", {
            "error": str(e),
            "message": f"Failed to ingest '{filename}': {str(e)}"
        })
    finally:
        # Clean up temporary upload file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass
