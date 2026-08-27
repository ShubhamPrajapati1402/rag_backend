import os
from typing import Type, Dict
from loguru import logger
from app.services.parsers.base import BaseParser

class ParserRegistry:
    """
    Registry mapping file extensions (and eventually MIME types) to their respective parser classes.
    Designed to easily plug in new format parsers (e.g., EPUB, JSONL) without touching ingest.py.
    """
    _parsers: Dict[str, Type[BaseParser]] = {}

    @classmethod
    def register(cls, extension: str, parser_class: Type[BaseParser]):
        cls._parsers[extension.lower()] = parser_class
        logger.debug(f"Registered parser {parser_class.__name__} for extension '{extension}'")

    @classmethod
    def get_parser(cls, file_path: str, **kwargs) -> BaseParser:
        """
        Retrieves the appropriate parser instance based on the file extension.
        Future enhancement: Use python-magic/mimetypes here for content-based detection.
        """
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        parser_class = cls._parsers.get(ext)
        if not parser_class:
            raise ValueError(f"Unsupported file format: {ext}. No parser registered for this extension.")
            
        return parser_class(**kwargs)
