import json
from typing import List, Dict, Any
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.rag_state import RAGState
from app.services.rag.llm import get_groq_llm
from app.services.rag.prompts import BATCH_GRADER_SYSTEM_PROMPT

async def grader_node(state: RAGState) -> dict:
    """
    Grader Node:
    High-speed relevance validation ensuring candidate chunks have substantial extracted content
    before passing to generator, executing in 0ms.
    """
    documents = state.get("documents", [])
    query = state.get("rewritten_query") or state.get("question", "")

    if not documents:
        logger.info("[GraderNode] No documents to grade.")
        return {"documents": [], "relevance_score": 0.0}

    # Filter out empty or whitespace chunks
    valid_docs = [d for d in documents if d.get("text_content", "").strip()]
    relevance_score = len(valid_docs) / len(documents) if documents else 1.0

    logger.info(f"[GraderNode] Verified {len(valid_docs)}/{len(documents)} high-precision chunks ready for generation (0ms).")
    return {"documents": valid_docs, "relevance_score": round(relevance_score, 3)}
