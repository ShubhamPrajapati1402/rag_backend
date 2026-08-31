import json
import random
from typing import List, Dict, Any, Optional
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage

from app.db.session import SessionLocal
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.rag.llm import get_llm, extract_text_content

SYNTHETIC_QA_PROMPT = """You are an expert QA dataset curator for an enterprise document intelligence benchmark.
Based ONLY on the provided document text excerpt, create {count} diverse, high-quality test questions that can be answered using this document.

For each question:
1. "question": A natural, realistic user question (e.g. asking for specific facts, tables, definitions, names, or metrics).
2. "ground_truth": The concise, exact factual answer with supporting details directly present in the excerpt.
3. "key_fact": A key phrase or number that MUST be present in the correct answer.

Document Name: {doc_name}
Excerpt:
\"\"\"{excerpt}\"\"\"

Respond with ONLY a valid JSON object matching this schema:
{{
  "test_cases": [
    {{
      "question": "What is ...?",
      "ground_truth": "...",
      "key_fact": "..."
    }}
  ]
}}"""

class SyntheticTestGenerator:
    """
    Dynamically generates realistic QA evaluation datasets from any document
    in PostgreSQL on the fly.
    """

    @classmethod
    async def generate_tests_for_document(
        cls,
        document_id: int,
        count: int = 3
    ) -> List[Dict[str, Any]]:
        """Generates synthetic QA test pairs for a specific document."""
        db = SessionLocal()
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                logger.error(f"[SyntheticGenerator] Document ID {document_id} not found.")
                return []

            chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
            if not chunks:
                logger.warning(f"[SyntheticGenerator] No chunks found for document '{doc.filename}'.")
                return []

            # Sample rich chunks (avoiding headers/empty chunks)
            rich_chunks = [c for c in chunks if len(c.text_content.strip()) > 150]
            if not rich_chunks:
                rich_chunks = chunks

            sample_chunks = random.sample(rich_chunks, min(len(rich_chunks), 3))
            combined_excerpt = "\n\n---\n\n".join([c.text_content for c in sample_chunks])[:3500]

            llm = get_llm(temperature=0.4)
            resp = await llm.ainvoke([
                SystemMessage(content="You are an expert test dataset creator."),
                HumanMessage(content=SYNTHETIC_QA_PROMPT.format(
                    count=count,
                    doc_name=doc.filename,
                    excerpt=combined_excerpt
                ))
            ])

            content = extract_text_content(resp.content).strip()
            test_cases = []
            if "{" in content and "}" in content:
                data = json.loads(content[content.find("{"):content.rfind("}")+1])
                raw_cases = data.get("test_cases", [])
                for tc in raw_cases:
                    test_cases.append({
                        "document_id": doc.id,
                        "document_name": doc.filename,
                        "question": tc.get("question", ""),
                        "ground_truth": tc.get("ground_truth", ""),
                        "key_fact": tc.get("key_fact", "")
                    })

            logger.info(f"[SyntheticGenerator] Generated {len(test_cases)} dynamic test cases for '{doc.filename}'.")
            return test_cases

        except Exception as e:
            logger.error(f"[SyntheticGenerator] Failed generating tests for doc {document_id}: {e}")
            return []
        finally:
            db.close()

    @classmethod
    async def generate_tests_for_all_documents(cls, cases_per_doc: int = 2) -> List[Dict[str, Any]]:
        """Generates synthetic QA test pairs for all active documents in the database."""
        db = SessionLocal()
        all_cases = []
        try:
            docs = db.query(Document).filter(Document.status == DocumentStatus.COMPLETED).all()
            logger.info(f"[SyntheticGenerator] Found {len(docs)} completed documents to benchmark.")
            for doc in docs:
                cases = await cls.generate_tests_for_document(doc.id, count=cases_per_doc)
                all_cases.extend(cases)
            return all_cases
        finally:
            db.close()
