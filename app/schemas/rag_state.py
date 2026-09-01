from typing import List, Dict, Any, Optional, TypedDict, Annotated
import operator

class Citation(TypedDict, total=False):
    document_id: Optional[int]
    filename: Optional[str]
    page_number: Optional[int]
    sheet_name: Optional[str]
    chunk_index: int
    text_preview: str

class RAGState(TypedDict):
    """
    State schema passed between nodes in the LangGraph RAG workflow.
    """
    messages: Annotated[List[Dict[str, str]], operator.add]
    summary: Optional[str]
    question: str
    rewritten_query: str
    documents: List[Dict[str, Any]]
    route: str  # "direct", "vectorstore", "fallback"
    generation: str
    citations: List[Dict[str, Any]]
    relevance_score: float
    session_id: Optional[str]
    user_id: Optional[int]
    document_ids: Optional[List[int]]
    model_provider: Optional[str]
    model_name: Optional[str]
    custom_api_key: Optional[str]
    custom_base_url: Optional[str]
    temperature: Optional[float]
