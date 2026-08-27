import os
from typing import List, Dict, Any, Tuple
from loguru import logger
from bs4 import BeautifulSoup

from app.models.document_element import DocumentElement
from app.services.parsers.base import BaseParser, BaseValidator

class HTMLParser(BaseParser):
    """
    Parser for HTML files using BeautifulSoup.
    Extracts text while trying to preserve basic semantics (headings, paragraphs, tables).
    """
    def parse(self, file_path: str, **kwargs) -> List[DocumentElement]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"HTML file not found: {file_path}")
            
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            
        elements = []
        heading_path = []
        current_heading_level = 0
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'table']):
            if tag.name.startswith('h'):
                level = int(tag.name[1])
                text = tag.get_text(strip=True)
                if not text:
                    continue
                    
                current_heading_level = level
                heading_path = heading_path[:current_heading_level - 1]
                heading_path.append(text)
                
                elements.append(DocumentElement(
                    element_type="title",
                    content=text,
                    metadata={"source_type": "html", "heading_path": list(heading_path), "level": current_heading_level}
                ))
                
            elif tag.name == 'p':
                text = tag.get_text(separator=' ', strip=True)
                if text:
                    elements.append(DocumentElement(
                        element_type="text",
                        content=text,
                        metadata={"source_type": "html", "heading_path": list(heading_path)}
                    ))
                    
            elif tag.name == 'table':
                # Simplified table extraction
                for row in tag.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    row_text = " | ".join(cell.get_text(strip=True) for cell in cells)
                    if row_text.strip():
                        elements.append(DocumentElement(
                            element_type="table_row",
                            content=row_text,
                            metadata={"source_type": "html", "heading_path": list(heading_path)}
                        ))
                        
        logger.info(f"Successfully extracted {len(elements)} elements from HTML.")
        return elements

    def chunk(self, elements: List[DocumentElement]) -> List[Dict[str, Any]]:
        """
        Heading-aware chunking for HTML.
        """
        chunks = []
        current_chunk_text = ""
        current_metadata = {"source_type": "html"}
        chunk_index = 0
        
        for el in elements:
            meta = el.metadata
            path_str = " > ".join(meta.get("heading_path", [])) if "heading_path" in meta else ""
            
            if path_str != current_metadata.get("_path_str") and current_chunk_text.strip():
                chunks.append({
                    "chunk_index": chunk_index,
                    "text_content": current_chunk_text.strip(),
                    "metadata_json": current_metadata,
                    "page_number": None
                })
                chunk_index += 1
                current_chunk_text = ""
            
            if el.element_type == "title":
                current_chunk_text += f"\n\n{el.content}\n"
            else:
                current_chunk_text += f"\n{el.content}"
                
            current_metadata = dict(meta)
            current_metadata["_path_str"] = path_str
            
        if current_chunk_text.strip():
            if "_path_str" in current_metadata:
                del current_metadata["_path_str"]
            chunks.append({
                "chunk_index": chunk_index,
                "text_content": current_chunk_text.strip(),
                "metadata_json": current_metadata,
                "page_number": None
            })
            
        logger.info(f"Successfully grouped HTML into {len(chunks)} chunks.")
        return chunks

    def get_validator(self) -> BaseValidator:
        return HTMLValidator()


class HTMLValidator(BaseValidator):
    def validate(self, chunks: List[Dict[str, Any]], **kwargs) -> Tuple[str, str, List[Any]]:
        if not chunks:
            return "WARNING: HTML file is empty or no chunks produced.", "WARNING", []
            
        total_chars = sum(len(c["text_content"]) for c in chunks)
        
        report = []
        report.append("-" * 40)
        report.append("HTML INGESTION VALIDATION REPORT")
        report.append("-" * 40)
        report.append(f"Total chunks: {len(chunks)}")
        report.append(f"Total characters: {total_chars}")
        
        status = "PASS" if total_chars > 0 else "WARNING"
            
        report.append(f"\nFINAL RESULT\n------------\n{status}")
        return "\n".join(report), status, []
