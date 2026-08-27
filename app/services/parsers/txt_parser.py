import os
from typing import List, Dict, Any, Tuple
from loguru import logger

from app.models.document_element import DocumentElement
from app.services.parsers.base import BaseParser, BaseValidator

class TXTParser(BaseParser):
    """
    Parser for plain text files.
    """
    def parse(self, file_path: str, **kwargs) -> List[DocumentElement]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Text file not found: {file_path}")
            
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Treat the entire text file as one big element, or split by double newlines (paragraphs)
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        
        elements = []
        for p in paragraphs:
            elements.append(DocumentElement(
                element_type="text",
                content=p,
                metadata={"source_type": "txt"}
            ))
            
        logger.info(f"Successfully extracted {len(elements)} paragraphs from TXT.")
        return elements

    def chunk(self, elements: List[DocumentElement]) -> List[Dict[str, Any]]:
        """
        Simple fixed-size or paragraph grouping chunking.
        For plain text, grouping by a fixed number of paragraphs is a safe default,
        but falls back to arbitrary slicing if a paragraph is too massive.
        """
        chunks = []
        current_chunk_text = ""
        chunk_index = 0
        max_chunk_size = 1000
        
        for el in elements:
            # If a single paragraph is gigantic (no double newlines in the file)
            if len(el.content) > max_chunk_size * 2:
                # First, flush whatever we currently have
                if current_chunk_text.strip():
                    chunks.append({
                        "chunk_index": chunk_index,
                        "text_content": current_chunk_text.strip(),
                        "metadata_json": {"source_type": "txt"},
                        "page_number": None
                    })
                    chunk_index += 1
                    current_chunk_text = ""
                
                # Then slice this gigantic element into hard constraints
                text_remaining = el.content
                while len(text_remaining) > 0:
                    slice_len = min(max_chunk_size, len(text_remaining))
                    # Try to find a space near the cutoff to avoid cutting words
                    if slice_len == max_chunk_size:
                        last_space = text_remaining.rfind(' ', 0, slice_len)
                        if last_space != -1 and last_space > slice_len * 0.8:
                            slice_len = last_space
                            
                    chunk_text = text_remaining[:slice_len].strip()
                    if chunk_text:
                        chunks.append({
                            "chunk_index": chunk_index,
                            "text_content": chunk_text,
                            "metadata_json": {"source_type": "txt"},
                            "page_number": None
                        })
                        chunk_index += 1
                    text_remaining = text_remaining[slice_len:]
                continue
                
            # Normal logic for reasonably sized paragraphs
            if len(current_chunk_text) + len(el.content) > max_chunk_size and current_chunk_text.strip():
                chunks.append({
                    "chunk_index": chunk_index,
                    "text_content": current_chunk_text.strip(),
                    "metadata_json": {"source_type": "txt"},
                    "page_number": None
                })
                chunk_index += 1
                current_chunk_text = ""
                
            current_chunk_text += f"{el.content}\n\n"
            
        if current_chunk_text.strip():
            chunks.append({
                "chunk_index": chunk_index,
                "text_content": current_chunk_text.strip(),
                "metadata_json": {"source_type": "txt"},
                "page_number": None
            })
            
        logger.info(f"Successfully grouped TXT into {len(chunks)} chunks.")
        return chunks

    def get_validator(self) -> BaseValidator:
        return TXTValidator()


class TXTValidator(BaseValidator):
    def validate(self, chunks: List[Dict[str, Any]], **kwargs) -> Tuple[str, str, List[Any]]:
        if not chunks:
            return "WARNING: Text file is empty or no chunks produced.", "WARNING", []
            
        total_chars = sum(len(c["text_content"]) for c in chunks)
        
        report = []
        report.append("-" * 40)
        report.append("TXT INGESTION VALIDATION REPORT")
        report.append("-" * 40)
        report.append(f"Total chunks: {len(chunks)}")
        report.append(f"Total characters: {total_chars}")
        
        status = "PASS" if total_chars > 0 else "WARNING"
            
        report.append(f"\nFINAL RESULT\n------------\n{status}")
        return "\n".join(report), status, []
