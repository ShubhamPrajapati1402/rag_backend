import os
import pandas as pd
from typing import List, Dict, Any, Tuple
from loguru import logger

from app.models.document_element import DocumentElement
from app.services.parsers.base import BaseParser, BaseValidator

class CSVParser(BaseParser):
    """
    Parser for CSV files using pandas.
    Preserves tabular structure by generating text representations of rows with headers.
    """
    def parse(self, file_path: str, **kwargs) -> List[DocumentElement]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV file not found: {file_path}")
            
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            raise ValueError(f"Failed to parse CSV: {e}")
            
        elements = []
        headers = df.columns.tolist()
        
        # We save the dataframe metadata, but we convert rows into readable text blocks
        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            # Create a string representation: "Column1: Value1 | Column2: Value2"
            content_parts = []
            for col in headers:
                val = row_dict.get(col)
                if pd.notna(val):
                    content_parts.append(f"{col}: {val}")
                    
            content = " | ".join(content_parts)
            
            elements.append(DocumentElement(
                element_type="table_row",
                content=content,
                metadata={
                    "source_type": "csv",
                    "row_index": int(idx),
                    "headers": headers,
                    "raw_json": row_dict
                }
            ))
            
        logger.info(f"Successfully extracted {len(elements)} rows from CSV.")
        return elements

    def chunk(self, elements: List[DocumentElement]) -> List[Dict[str, Any]]:
        """
        Group rows into chunks (e.g., 20 rows per chunk).
        """
        chunks = []
        rows_per_chunk = 20
        
        current_chunk_rows = []
        chunk_index = 0
        
        for el in elements:
            current_chunk_rows.append(el.content)
            
            if len(current_chunk_rows) >= rows_per_chunk:
                chunks.append({
                    "chunk_index": chunk_index,
                    "text_content": "\n".join(current_chunk_rows),
                    "metadata_json": {"source_type": "csv", "rows": rows_per_chunk},
                    "page_number": None
                })
                chunk_index += 1
                current_chunk_rows = []
                
        if current_chunk_rows:
            chunks.append({
                "chunk_index": chunk_index,
                "text_content": "\n".join(current_chunk_rows),
                "metadata_json": {"source_type": "csv", "rows": len(current_chunk_rows)},
                "page_number": None
            })
            
        logger.info(f"Successfully grouped CSV into {len(chunks)} chunks.")
        return chunks

    def get_validator(self) -> BaseValidator:
        return CSVValidator()


class CSVValidator(BaseValidator):
    def validate(self, chunks: List[Dict[str, Any]], **kwargs) -> Tuple[str, str, List[Any]]:
        if not chunks:
            return "WARNING: CSV file is empty or no chunks produced.", "WARNING", []
            
        total_rows = sum(c["metadata_json"].get("rows", 0) for c in chunks)
        
        report = []
        report.append("-" * 40)
        report.append("CSV INGESTION VALIDATION REPORT")
        report.append("-" * 40)
        report.append(f"Total chunks: {len(chunks)}")
        report.append(f"Total rows: {total_rows}")
        
        status = "PASS" if total_rows > 0 else "WARNING"
            
        report.append(f"\nFINAL RESULT\n------------\n{status}")
        return "\n".join(report), status, []
