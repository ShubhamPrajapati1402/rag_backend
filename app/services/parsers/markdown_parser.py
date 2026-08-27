import os
import time
from typing import List, Dict, Any, Tuple
from loguru import logger
from markdown_it import MarkdownIt

from app.models.document_element import DocumentElement
from app.services.parsers.base import BaseParser, BaseValidator

class MarkdownParser(BaseParser):
    """
    Parser for Markdown files.
    Preserves structural hierarchy by tracking heading paths.
    """
    def __init__(self):
        self.md = MarkdownIt()

    def parse(self, file_path: str, **kwargs) -> List[DocumentElement]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Markdown file not found: {file_path}")
            
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        tokens = self.md.parse(content)
        
        elements = []
        heading_path = []
        
        # Simple stack to track heading levels (h1=1, h2=2, etc.)
        current_heading_level = 0
        
        in_heading = False
        current_heading_text = ""
        
        for token in tokens:
            if token.type == "heading_open":
                in_heading = True
                level = int(token.tag[1])  # 'h1' -> 1
                current_heading_level = level
                
            elif token.type == "heading_close":
                in_heading = False
                # Adjust heading path based on level
                # Keep elements strictly higher in the hierarchy
                heading_path = heading_path[:current_heading_level - 1]
                heading_path.append(current_heading_text)
                
                elements.append(DocumentElement(
                    element_type="title",
                    content=current_heading_text,
                    metadata={"source_type": "markdown", "heading_path": list(heading_path), "level": current_heading_level}
                ))
                current_heading_text = ""
                
            elif token.type == "inline":
                if in_heading:
                    current_heading_text += token.content
                else:
                    # Generic inline text (usually inside a paragraph, list item, etc.)
                    # We just save it as text. More robust parsing can differentiate list items and paragraphs.
                    if token.content.strip():
                        elements.append(DocumentElement(
                            element_type="text",
                            content=token.content,
                            metadata={"source_type": "markdown", "heading_path": list(heading_path)}
                        ))
                        
            elif token.type == "fence" or token.type == "code_block":
                elements.append(DocumentElement(
                    element_type="code",
                    content=token.content,
                    metadata={"source_type": "markdown", "heading_path": list(heading_path), "language": token.info}
                ))
                
        logger.info(f"Successfully extracted {len(elements)} elements from Markdown.")
        return elements

    def chunk(self, elements: List[DocumentElement]) -> List[Dict[str, Any]]:
        """
        Heading-aware chunking. Groups elements by their heading path.
        """
        chunks = []
        current_chunk_text = ""
        current_metadata = {}
        chunk_index = 0
        
        for el in elements:
            # If the heading path changes, start a new chunk
            meta = el.metadata
            path_str = " > ".join(meta.get("heading_path", []))
            
            if path_str != current_metadata.get("_path_str") and current_chunk_text.strip():
                chunks.append({
                    "chunk_index": chunk_index,
                    "text_content": current_chunk_text.strip(),
                    "metadata_json": current_metadata,
                    "page_number": None
                })
                chunk_index += 1
                current_chunk_text = ""
            
            # Combine content
            if el.element_type == "title":
                current_chunk_text += f"\n\n{el.content}\n"
            else:
                current_chunk_text += f"\n{el.content}"
                
            current_metadata = dict(meta)
            current_metadata["_path_str"] = path_str
            
        # Add final chunk
        if current_chunk_text.strip():
            # Clean up the internal _path_str
            if "_path_str" in current_metadata:
                del current_metadata["_path_str"]
                
            chunks.append({
                "chunk_index": chunk_index,
                "text_content": current_chunk_text.strip(),
                "metadata_json": current_metadata,
                "page_number": None
            })
            
        logger.info(f"Successfully grouped Markdown into {len(chunks)} logical chunks.")
        return chunks

    def get_validator(self) -> BaseValidator:
        return MarkdownValidator()


class MarkdownValidator(BaseValidator):
    def validate(self, chunks: List[Dict[str, Any]], **kwargs) -> Tuple[str, str, List[Any]]:
        if not chunks:
            return "WARNING: Markdown file is empty or no chunks produced.", "WARNING", []
            
        total_chars = sum(len(c["text_content"]) for c in chunks)
        
        report = []
        report.append("-" * 40)
        report.append("MARKDOWN INGESTION VALIDATION REPORT")
        report.append("-" * 40)
        report.append(f"Total chunks: {len(chunks)}")
        report.append(f"Total characters: {total_chars}")
        
        status = "PASS"
        if total_chars == 0:
            status = "WARNING"
            
        report.append(f"\nFINAL RESULT\n------------\n{status}")
        return "\n".join(report), status, []
