from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from app.models.document_element import DocumentElement

class BaseParser(ABC):
    """
    Abstract interface for all format-specific document parsers.
    """
    @abstractmethod
    def parse(self, file_path: str, **kwargs) -> List[DocumentElement]:
        """
        Parses a file and extracts a list of Unified DocumentElements.
        """
        pass
        
    @abstractmethod
    def chunk(self, elements: List[DocumentElement]) -> List[Dict[str, Any]]:
        """
        Chunks the elements into logical blocks.
        Must return a list of dictionaries where each dict has:
        - chunk_index (int)
        - text_content (str)
        - metadata_json (dict)
        - optionally page_number (int)
        """
        pass

class BaseValidator(ABC):
    """
    Abstract interface for format-specific validation.
    """
    @abstractmethod
    def validate(self, chunks: List[Dict[str, Any]], **kwargs) -> Tuple[str, str, List[Any]]:
        """
        Validates the chunks and returns:
        1. A detailed report string (for the terminal).
        2. A status string ("PASS", "WARNING", "FAIL").
        3. A list of fallback identifiers (e.g., page numbers, row blocks) if a targeted re-run is needed.
        """
        pass
