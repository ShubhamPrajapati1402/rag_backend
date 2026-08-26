import os
import json
import time
import unicodedata
from collections import defaultdict
from typing import List, Dict, Any

class DocumentValidator:
    def __init__(self, raw_elements):
        self.raw_elements = raw_elements
        self.final_chunks = []
        self.timings = {}
        
        self.page_stats = defaultdict(lambda: {
            "raw_elements": 0,
            "raw_chars": 0,
            "raw_words": 0,
            "raw_tables": 0,
            "raw_images": 0,
            "chunks": 0,
            "chunk_chars": 0,
            "status": "OK"
        })
        
        self.element_types = defaultdict(int)
        self.tables = []
        
    def record_timing(self, name: str, duration: float):
        self.timings[name] = duration
        
    def normalize_text(self, text: str) -> str:
        if not text:
            return ""
        # Unicode normalize using NFKC
        text = unicodedata.normalize('NFKC', text)
        # Lowercase
        text = text.lower()
        # Normalize whitespace (replaces all runs of whitespace/newlines with a single space)
        text = " ".join(text.split())
        return text

    def run_validation(self, chunks: List[dict]):
        self.final_chunks = chunks
        
        val_start = time.time()
        
        # A. RAW EXTRACTION VALIDATION & B. PAGE COVERAGE
        total_raw_chars = 0
        total_raw_words = 0
        elements_missing_page = 0
        elements_empty_text = 0
        
        for idx, el in enumerate(self.raw_elements):
            el_type = type(el).__name__
            self.element_types[el_type] += 1
            
            text = el.text if hasattr(el, 'text') and el.text else ""
            chars = len(text)
            words = len(text.split())
            
            total_raw_chars += chars
            total_raw_words += words
            
            page = el.metadata.page_number if hasattr(el, 'metadata') and hasattr(el.metadata, 'page_number') and el.metadata.page_number else None
            
            if page is None:
                elements_missing_page += 1
            else:
                self.page_stats[page]["raw_elements"] += 1
                self.page_stats[page]["raw_chars"] += chars
                self.page_stats[page]["raw_words"] += words
                if el_type == "Table":
                    self.page_stats[page]["raw_tables"] += 1
                elif el_type == "Image":
                    self.page_stats[page]["raw_images"] += 1
                    
            if chars < 3:
                elements_empty_text += 1
                
            # C. TABLE VALIDATION
            if el_type == "Table":
                self.tables.append({
                    "element_index": idx,
                    "page": page,
                    "length": chars,
                    "text": text,
                    "status": "PENDING"
                })

        # D. CHUNK VALIDATION
        empty_chunks = 0
        missing_meta_chunks = 0
        total_chunk_chars = 0
        chunk_issues = []
        
        for i, chunk in enumerate(self.final_chunks):
            if chunk["chunk_index"] != i:
                chunk_issues.append(f"Chunk {i} has mismatched index {chunk['chunk_index']}")
                
            text = chunk.get("text_content", "")
            if not text:
                empty_chunks += 1
                
            total_chunk_chars += len(text)
            
            page = chunk.get("page_number")
            if page is None:
                missing_meta_chunks += 1
            else:
                self.page_stats[page]["chunks"] += 1
                self.page_stats[page]["chunk_chars"] += len(text)
                
        # E. CONTENT COVERAGE
        # Build normalized representation of final chunks
        chunk_texts_norm = [self.normalize_text(c.get("text_content", "")) for c in self.final_chunks]
        giant_chunk_string = " ||| ".join(chunk_texts_norm) # Just for fallback matching
        
        elements_fully_represented = 0
        elements_partially_represented = 0
        elements_missing = 0
        
        # F. DUPLICATION ANALYSIS
        suspicious_duplicates = []
        
        coverage_details = []
        
        for idx, el in enumerate(self.raw_elements):
            text = el.text if hasattr(el, 'text') and el.text else ""
            if len(text) < 10:
                continue # Skip tiny fragments for coverage matching to avoid false positives
                
            norm_text = self.normalize_text(text)
            if not norm_text:
                continue
                
            matched_indices = []
            for c_idx, c_norm in enumerate(chunk_texts_norm):
                if norm_text in c_norm:
                    matched_indices.append(c_idx)
            
            status = "MISSING"
            coverage_pct = 0.0
            
            if len(matched_indices) > 0:
                status = "FULLY_REPRESENTED"
                coverage_pct = 100.0
                elements_fully_represented += 1
                
                # Check for table status
                for t in self.tables:
                    if t["element_index"] == idx:
                        t["status"] = "OK"
                        
                # Duplication analysis (normal overlap hits 2 chunks, maybe 3. If > 3, suspicious)
                if len(matched_indices) > 3:
                    suspicious_duplicates.append({
                        "page": el.metadata.page_number if hasattr(el, 'metadata') and hasattr(el.metadata, 'page_number') else None,
                        "element_index": idx,
                        "matched_chunks": matched_indices,
                        "text_preview": text[:100]
                    })
            else:
                # Try partial match or fallback
                # If 80% of the normalized text is in the giant string, consider partial
                half_len = len(norm_text) // 2
                if half_len > 10 and (norm_text[:half_len] in giant_chunk_string or norm_text[half_len:] in giant_chunk_string):
                    status = "PARTIALLY_REPRESENTED"
                    coverage_pct = 50.0
                    elements_partially_represented += 1
                else:
                    status = "MISSING"
                    elements_missing += 1
                    # Update table status
                    for t in self.tables:
                        if t["element_index"] == idx:
                            t["status"] = "ERROR_MISSING"

            coverage_details.append({
                "element_index": idx,
                "type": type(el).__name__,
                "page": el.metadata.page_number if hasattr(el, 'metadata') and hasattr(el.metadata, 'page_number') else None,
                "status": status,
                "matched_chunks": matched_indices,
                "text_preview": text[:100]
            })

        # B. PAGE COVERAGE HEURISTICS
        pages_missing = 0
        suspicious_pages = 0
        for p, stats in self.page_stats.items():
            if stats["raw_chars"] == 0 and stats["raw_images"] == 0:
                stats["status"] = "WARNING_EMPTY"
                suspicious_pages += 1
            elif stats["raw_chars"] > 50 and stats["chunks"] == 0:
                # Content extracted but no chunks assigned to this page
                stats["status"] = "ERROR_LOST_CHUNKS"
                pages_missing += 1
                
        val_duration = time.time() - val_start
        self.record_timing("validation_duration", val_duration)
        
        # 9. GENERATE VALIDATION REPORT
        report_lines = []
        report_lines.append("----------------------------------------")
        report_lines.append("PDF INGESTION VALIDATION REPORT")
        report_lines.append("----------------------------------------")
        report_lines.append("")
        
        report_lines.append("PERFORMANCE & TIMINGS")
        report_lines.append("---------------------")
        for k, v in self.timings.items():
            report_lines.append(f"{k}: {v:.2f}s")
        report_lines.append("")

        report_lines.append("RAW EXTRACTION")
        report_lines.append("--------------")
        report_lines.append(f"Total elements: {len(self.raw_elements)}")
        report_lines.append(f"Total characters: {total_raw_chars}")
        report_lines.append(f"Total words: {total_raw_words}")
        report_lines.append(f"Elements missing page meta: {elements_missing_page}")
        report_lines.append(f"Elements suspiciously short/empty: {elements_empty_text}")
        report_lines.append("")
        report_lines.append("Element types:")
        for k, v in sorted(self.element_types.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"  {k}: {v}")
        report_lines.append("")
        
        report_lines.append("PAGE COVERAGE")
        report_lines.append("-------------")
        report_lines.append(f"Pages detected: {len(self.page_stats)}")
        report_lines.append(f"Pages missing chunks: {pages_missing}")
        report_lines.append(f"Suspicious pages: {suspicious_pages}")
        report_lines.append("")
        
        report_lines.append("TABLE VALIDATION")
        report_lines.append("----------------")
        tables_ok = sum(1 for t in self.tables if t["status"] == "OK")
        report_lines.append(f"Tables detected: {len(self.tables)}")
        report_lines.append(f"Tables preserved: {tables_ok}")
        report_lines.append(f"Tables missing: {len(self.tables) - tables_ok}")
        report_lines.append("")
        
        report_lines.append("CHUNK VALIDATION")
        report_lines.append("----------------")
        report_lines.append(f"Total chunks: {len(self.final_chunks)}")
        report_lines.append(f"Empty chunks: {empty_chunks}")
        report_lines.append(f"Chunks without page metadata: {missing_meta_chunks}")
        if chunk_issues:
            report_lines.append("Chunk Sequence Issues:")
            for iss in chunk_issues[:5]:
                report_lines.append(f"  - {iss}")
        report_lines.append("")
        
        report_lines.append("CONTENT COVERAGE (elements > 10 chars)")
        report_lines.append("----------------")
        report_lines.append(f"Elements fully represented: {elements_fully_represented}")
        report_lines.append(f"Elements partially represented: {elements_partially_represented}")
        report_lines.append(f"Elements missing: {elements_missing}")
        report_lines.append("")
        
        report_lines.append("DUPLICATION")
        report_lines.append("-----------")
        report_lines.append(f"Suspicious duplicates (matched >3 chunks): {len(suspicious_duplicates)}")
        report_lines.append("")
        
        report_lines.append("PAGE SUMMARY")
        report_lines.append("------------")
        report_lines.append("Page | Raw Elems | Raw Chars | Chunks | Chunk Chars | Tables | Status")
        for p in sorted(self.page_stats.keys()):
            s = self.page_stats[p]
            report_lines.append(f"{p:<4} | {s['raw_elements']:<9} | {s['raw_chars']:<9} | {s['chunks']:<6} | {s['chunk_chars']:<11} | {s['raw_tables']:<6} | {s['status']}")
        report_lines.append("")
        
        final_status = "PASS"
        if elements_missing > 0 or tables_ok < len(self.tables) or empty_chunks > 0:
            final_status = "FAIL"
        elif suspicious_pages > 0 or pages_missing > 0:
            final_status = "WARNING"
            
        report_lines.append("FINAL RESULT")
        report_lines.append("------------")
        report_lines.append(final_status)
        
        report_text = "\n".join(report_lines)
        
        return report_text
