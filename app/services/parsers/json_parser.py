import os
import json
from typing import List, Dict, Any, Tuple
from loguru import logger

from app.models.document_element import DocumentElement
from app.services.parsers.base import BaseParser, BaseValidator

class JSONParser(BaseParser):
    """
    Parser for JSON files.
    Preserves object hierarchy by tracking paths (e.g., 'customer.address.city').
    """
    def parse(self, file_path: str, **kwargs) -> List[DocumentElement]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"JSON file not found: {file_path}")
            
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON: {e}")
                
        elements = []
        
        def traverse(obj, path):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    traverse(v, path + [str(k)])
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    traverse(v, path + [f"[{i}]"])
            else:
                # Leaf node
                if obj is not None and str(obj).strip():
                    elements.append(DocumentElement(
                        element_type="json_value",
                        content=str(obj),
                        metadata={"source_type": "json", "json_path": ".".join(path) or "$"}
                    ))
                    
        traverse(data, [])
        logger.info(f"Successfully extracted {len(elements)} leaf values from JSON.")
        return elements

    def chunk(self, elements: List[DocumentElement]) -> List[Dict[str, Any]]:
        """
        Groups nearby JSON paths together to provide context to the LLM.
        """
        chunks = []
        current_chunk_text = ""
        current_metadata = {"source_type": "json"}
        chunk_index = 0
        
        for el in elements:
            path = el.metadata.get("json_path", "")
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
            
        logger.info(f"Successfully grouped JSON into {len(chunks)} chunks.")
        return chunks

    def get_validator(self) -> BaseValidator:
        return JSONValidator()


class JSONValidator(BaseValidator):
    def validate(self, chunks: List[Dict[str, Any]], **kwargs) -> Tuple[str, str, List[Any]]:
        if not chunks:
            return "WARNING: JSON file is empty or no chunks produced.", "WARNING", []
            
        total_chars = sum(len(c["text_content"]) for c in chunks)
        
        report = []
        report.append("-" * 40)
        report.append("JSON INGESTION VALIDATION REPORT")
        report.append("-" * 40)
        report.append(f"Total chunks: {len(chunks)}")
        report.append(f"Total characters: {total_chars}")
        
        status = "PASS" if total_chars > 0 else "WARNING"
            
        report.append(f"\nFINAL RESULT\n------------\n{status}")
        return "\n".join(report), status, []
