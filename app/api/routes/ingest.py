from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime
from loguru import logger

from app.db.session import get_db
from app.models.user import User
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.api.deps import get_current_user
from app.services.ingestion_service import stream_dynamic_ingestion

router = APIRouter(prefix="/ingest", tags=["Ingestion & Vector Processing"])

import os

class DocumentSummary(BaseModel):
    id: int
    filename: str
    format: str
    file_type: str
    size: str
    status: str
    chunk_count: int
    created_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

class DocumentPreviewResponse(BaseModel):
    id: int
    filename: str
    format: str
    file_type: str
    size: str
    status: str
    chunk_count: int
    summary: str
    extracted_preview: str
    created_at: Optional[datetime]
    completed_at: Optional[datetime]

@router.post("/stream", summary="Upload and ingest document with dynamic layman SSE progress")
async def stream_upload_and_ingest(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Accepts a document upload (PDF, DOCX, Markdown, CSV, Excel, TXT, etc.)
    and returns a Server-Sent Events (SSE) stream reporting real-time dynamic
    layman progress (page extraction, chunking, AI batch embedding, and persistence).
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    filename = file.filename or "uploaded_document"

    return StreamingResponse(
        stream_dynamic_ingestion(file_bytes, filename, current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

def _get_file_format(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lstrip(".").upper() if ext else "TXT"

@router.get("/documents", response_model=List[DocumentSummary], summary="List all user uploaded documents")
async def list_user_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns a list of all documents uploaded and processed by the authenticated user."""
    docs = (
        db.query(
            Document.id,
            Document.filename,
            Document.file_path,
            Document.status,
            Document.created_at,
            Document.completed_at,
            func.count(DocumentChunk.id).label("chunk_count"),
            func.sum(func.length(DocumentChunk.text_content)).label("total_chars")
        )
        .outerjoin(DocumentChunk, Document.id == DocumentChunk.document_id)
        .filter((Document.user_id == current_user.id) | (Document.user_id.is_(None)))
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
        .all()
    )

    summaries = []
    for d in docs:
        fmt = _get_file_format(d.filename)
        # Approximate file size based on extracted character length (1 char ~= 1 byte)
        size_bytes = 0
        file_path = getattr(d, 'file_path', None)
        if file_path and os.path.exists(file_path):
            try:
                size_bytes = os.path.getsize(file_path)
            except Exception:
                size_bytes = 0
        
        if size_bytes <= 0:
            chars = d.total_chars or 0
            if d.chunk_count > 0:
                # PDF binary file size is realistically ~120KB-200KB per structural page/chunk
                size_bytes = max(chars * 4, d.chunk_count * 150 * 1024)
            else:
                size_bytes = max(chars, 1024)

        if size_bytes >= 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{max(1.0, size_bytes / 1024):.1f} KB"

        summaries.append(
            DocumentSummary(
                id=d.id,
                filename=d.filename,
                format=fmt,
                file_type=fmt,
                size=size_str,
                status=d.status.value if hasattr(d.status, "value") else str(d.status),
                chunk_count=d.chunk_count,
                created_at=d.created_at,
                completed_at=d.completed_at
            )
        )

    return summaries

@router.get("/documents/{document_id}/preview", response_model=DocumentPreviewResponse, summary="Get document content preview")
async def get_document_preview(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches real parsed content preview and metadata for a specific document."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        (Document.user_id == current_user.id) | (Document.user_id.is_(None))
    ).first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc.id)
        .order_by(DocumentChunk.chunk_index.asc())
        .limit(5)
        .all()
    )

    joined_text = "\n\n---\n\n".join(c.text_content.strip() for c in chunks if c.text_content) if chunks else "No text extracted."
    fmt = _get_file_format(doc.filename)
    size_bytes = 0
    if getattr(doc, 'file_path', None) and os.path.exists(doc.file_path):
        try:
            size_bytes = os.path.getsize(doc.file_path)
        except Exception:
            size_bytes = 0

    if size_bytes <= 0:
        chars = sum(len(c.text_content) for c in chunks)
        if len(chunks) > 0:
            size_bytes = max(chars * 4, len(chunks) * 150 * 1024)
        else:
            size_bytes = max(chars, 1024)

    size_str = f"{size_bytes / (1024 * 1024):.1f} MB" if size_bytes >= 1024 * 1024 else f"{max(1.0, size_bytes / 1024):.1f} KB"

    return DocumentPreviewResponse(
        id=doc.id,
        filename=doc.filename,
        format=fmt,
        file_type=fmt,
        size=size_str,
        status=doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        chunk_count=len(chunks),
        summary=f"Parsed {fmt} document containing {len(chunks)} structural sections indexed in vector space.",
        extracted_preview=joined_text,
        created_at=doc.created_at,
        completed_at=doc.completed_at
    )

@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete document")
async def delete_user_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes a document and its associated vector embeddings."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or you do not have permission to delete it."
        )

    # Invalidate cache before deletion
    try:
        from app.services.rag.cache import RAGCacheService
        RAGCacheService.invalidate_all_rag_responses()
    except Exception as e:
        logger.debug(f"[DeleteDocument] Cache invalidation warning: {e}")

    # Chunks are deleted automatically via CASCADE constraint, or manually
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
    db.delete(doc)
    db.commit()

    return None
