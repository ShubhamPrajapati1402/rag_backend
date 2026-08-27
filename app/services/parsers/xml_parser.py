import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple
from loguru import logger

from app.models.document_element import DocumentElement
from app.services.parsers.base import BaseParser, BaseValidator

class XMLParser(BaseParser):
    """
    Parser for XML files.
    Preserves node hierarchy by tracking paths (e.g., 'catalog.book.title').
    """
    def parse(self, file_path: str, **kwargs) -> List[DocumentElement]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"XML file not found: {file_path}")
            
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XML: {e}")
            
        elements = []
        
        def traverse(node, path):
            # Extract text from this node
            if node.text and node.text.strip():
                elements.append(DocumentElement(
                    element_type="xml_value",
                    content=node.text.strip(),
                    metadata={"source_type": "xml", "xml_path": ".".join(path)}
                ))
            
            # Extract attributes
            if node.attrib:
                for k, v in node.attrib.items():
                    elements.append(DocumentElement(
                        element_type="xml_attribute",
                        content=str(v).strip(),
                        metadata={"source_type": "xml", "xml_path": ".".join(path) + f"@{k}"}
                    ))
                    
            for child in node:
                traverse(child, path + [child.tag])
                
        traverse(root, [root.tag])
        logger.info(f"Successfully extracted {len(elements)} values from XML.")
        return elements

    def chunk(self, elements: List[DocumentElement]) -> List[Dict[str, Any]]:
        """
        Groups nearby XML paths together.
        """
        chunks = []
        current_chunk_text = ""
        current_metadata = {"source_type": "xml"}
        chunk_index = 0
        
        for el in elements:
            path = el.metadata.get("xml_path", "")
            val = el.content
            
            # Simple grouping by fixed character count (approx 1000)
            if len(current_chunk_text) > 1000:
                chunks.append({
                    "chunk_index": chunk_index,
                    "text_content": current_chunk_text.strip(),
                    "metadata_json": current_metadata,
                    "page_number": None
                })
                chunk_index += 1
                current_chunk_text = ""
                
            current_chunk_text += f"{path}: {val}\n"
            
        if current_chunk_text.strip():
            chunks.append({
                "chunk_index": chunk_index,
                "text_content": current_chunk_text.strip(),
                "metadata_json": current_metadata,
                "page_number": None
            })
            
        logger.info(f"Successfully grouped XML into {len(chunks)} chunks.")
        return chunks

    def get_validator(self) -> BaseValidator:
        return XMLValidator()


class XMLValidator(BaseValidator):
    def validate(self, chunks: List[Dict[str, Any]], **kwargs) -> Tuple[str, str, List[Any]]:
        if not chunks:
            return "WARNING: XML file is empty or no chunks produced.", "WARNING", []
            
        total_chars = sum(len(c["text_content"]) for c in chunks)
        
        report = []
        report.append("-" * 40)
        report.append("XML INGESTION VALIDATION REPORT")
        report.append("-" * 40)
        report.append(f"Total chunks: {len(chunks)}")
        report.append(f"Total characters: {total_chars}")
        
        status = "PASS" if total_chars > 0 else "WARNING"
            
        report.append(f"\nFINAL RESULT\n------------\n{status}")
        return "\n".join(report), status, []
