import os
import pandas as pd
from typing import List, Dict, Any, Tuple
from loguru import logger

from app.models.document_element import DocumentElement
from app.services.parsers.base import BaseParser, BaseValidator

class ExcelParser(BaseParser):
    """
    Parser for Excel files using pandas.
    Preserves sheet boundaries.
    """
    def parse(self, file_path: str, **kwargs) -> List[DocumentElement]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Excel file not found: {file_path}")
            
        try:
            # Read all sheets
            sheets = pd.read_excel(file_path, sheet_name=None)
        except Exception as e:
            raise ValueError(f"Failed to parse Excel file: {e}")
            
        elements = []
        for sheet_name, df in sheets.items():
            headers = df.columns.tolist()
            
            for idx, row in df.iterrows():
                row_dict = row.to_dict()
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
                        "source_type": "excel",
                        "sheet_name": sheet_name,
                        "row_index": int(idx),
                        "headers": headers
                    }
                ))
                
        logger.info(f"Successfully extracted {len(elements)} rows from {len(sheets)} sheets in Excel.")
        return elements

    def chunk(self, elements: List[DocumentElement]) -> List[Dict[str, Any]]:
        """
        Group rows by sheet, max 20 rows per chunk.
        NEVER spans a chunk across multiple sheets.
        """
        chunks = []
        rows_per_chunk = 20
        
        current_chunk_rows = []
        current_sheet = None
        chunk_index = 0
        
        for el in elements:
            sheet_name = el.metadata.get("sheet_name")
            
            # Flush chunk if sheet changes or max rows reached
            if current_sheet is not None and (sheet_name != current_sheet or len(current_chunk_rows) >= rows_per_chunk):
                chunks.append({
                    "chunk_index": chunk_index,
                    "text_content": "\n".join(current_chunk_rows),
                    "metadata_json": {"source_type": "excel", "sheet_name": current_sheet, "rows": len(current_chunk_rows)},
                    "page_number": None
                })
                chunk_index += 1
                current_chunk_rows = []
                
            current_sheet = sheet_name
            current_chunk_rows.append(el.content)
            
        if current_chunk_rows:
            chunks.append({
                "chunk_index": chunk_index,
                "text_content": "\n".join(current_chunk_rows),
                "metadata_json": {"source_type": "excel", "sheet_name": current_sheet, "rows": len(current_chunk_rows)},
                "page_number": None
            })
            
        logger.info(f"Successfully grouped Excel into {len(chunks)} chunks.")
        return chunks

    def get_validator(self) -> BaseValidator:
        return ExcelValidator()


class ExcelValidator(BaseValidator):
    def validate(self, chunks: List[Dict[str, Any]], **kwargs) -> Tuple[str, str, List[Any]]:
        if not chunks:
            return "WARNING: Excel file is empty or no chunks produced.", "WARNING", []
            
        total_rows = sum(c["metadata_json"].get("rows", 0) for c in chunks)
        sheets = set(c["metadata_json"].get("sheet_name") for c in chunks)
        
        report = []
        report.append("-" * 40)
        report.append("EXCEL INGESTION VALIDATION REPORT")
        report.append("-" * 40)
        report.append(f"Sheets detected: {len(sheets)} ({', '.join(str(s) for s in sheets)})")
        report.append(f"Total chunks: {len(chunks)}")
        report.append(f"Total rows: {total_rows}")
        
        status = "PASS" if total_rows > 0 else "WARNING"
            
        report.append(f"\nFINAL RESULT\n------------\n{status}")
        return "\n".join(report), status, []
