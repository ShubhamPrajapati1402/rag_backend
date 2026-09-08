from typing import List, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

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
    document_ids: Optional[List[Union[int, str]]] = Field(None, description="Optional list of document IDs or filenames to restrict search")
    model_provider: Optional[str] = Field("inbuilt", description="Model provider ('inbuilt', 'gemini', 'groq', 'openai', 'anthropic', 'deepseek', 'mistral', 'openrouter', 'custom')")
    model_name: Optional[str] = Field(None, description="Model identifier (e.g. 'gemini-3.6-flash', 'gpt-4o', 'claude-3-5-sonnet-latest')")
    api_key: Optional[str] = Field(None, description="Optional ephemeral API key override for this request")
    temperature: Optional[float] = Field(0.3, ge=0.0, le=2.0, description="Model sampling temperature")

    @field_validator("document_ids", mode="before")
    @classmethod
    def sanitize_document_ids(cls, v):
        if not v:
            return None
        if isinstance(v, (int, str)):
            v = [v]
        return list(v) if isinstance(v, (list, tuple)) else None

class ChatResponse(BaseModel):
    answer: str
    session_id: str
    title: str
    citations: List[CitationSchema] = []
    route_taken: str = "vectorstore"
    relevance_score: float = 1.0
    model_provider: str = "inbuilt"
    model_name: Optional[str] = None

class ChatMessageItem(BaseModel):
    id: str
    role: str
    content: str
    citations: Optional[List[CitationSchema]] = None
    route_taken: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    created_at: datetime

class ChatSessionSummary(BaseModel):
    id: str
    title: str
    model_provider: Optional[str] = "inbuilt"
    model_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

class ChatSessionDetail(BaseModel):
    id: str
    title: str
    model_provider: Optional[str] = "inbuilt"
    model_name: Optional[str] = None
    created_at: datetime
    messages: List[ChatMessageItem] = []
