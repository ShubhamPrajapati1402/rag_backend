from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class DocumentElement:
    """
    A unified, format-agnostic representation of a document element.
    This structure ensures the core ingestion pipeline can handle PDF, CSV, DOCX, Markdown, etc.
    without knowing the specifics of their parsers.
    """
    element_type: str  # e.g., 'text', 'title', 'table', 'list', 'code', 'image'
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
