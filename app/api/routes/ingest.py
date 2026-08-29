from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.models.user import User
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.api.deps import get_current_user
from app.services.ingestion_service import stream_dynamic_ingestion

router = APIRouter(prefix="/ingest", tags=["Ingestion & Vector Processing"])

class DocumentSummary(BaseModel):
    id: int
    filename: str
    status: str
    chunk_count: int
    created_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

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
            Document.status,
            Document.created_at,
            Document.completed_at,
            func.count(DocumentChunk.id).label("chunk_count")
        )
        .outerjoin(DocumentChunk, Document.id == DocumentChunk.document_id)
        .filter(Document.user_id == current_user.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
        .all()
    )

    return [
        DocumentSummary(
            id=d.id,
            filename=d.filename,
            status=d.status.value if hasattr(d.status, "value") else str(d.status),
            chunk_count=d.chunk_count,
            created_at=d.created_at,
            completed_at=d.completed_at
        )
        for d in docs
    ]

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    db.delete(doc)
    db.commit()
    return None
