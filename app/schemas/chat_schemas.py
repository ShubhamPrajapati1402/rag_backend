from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

class CitationSchema(BaseModel):
    document_id: Optional[int] = None
    filename: Optional[str] = None
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    chunk_index: int = 0
    text_preview: str = ""

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question or prompt")
    session_id: Optional[str] = Field(None, description="Existing session UUID or None to create new session")
    document_ids: Optional[List[int]] = Field(None, description="Optional list of document IDs to restrict search")

class ChatResponse(BaseModel):
    answer: str
    session_id: str
    title: str
    citations: List[CitationSchema] = []
    route_taken: str = "vectorstore"
    relevance_score: float = 1.0

class ChatMessageItem(BaseModel):
    id: str
    role: str
    content: str
    citations: Optional[List[CitationSchema]] = None
    route_taken: Optional[str] = None
    created_at: datetime

class ChatSessionSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

class ChatSessionDetail(BaseModel):
    id: str
    title: str
    created_at: datetime
    messages: List[ChatMessageItem] = []
