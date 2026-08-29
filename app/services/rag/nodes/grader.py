import json
import asyncio
from typing import List, Dict, Any
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.rag_state import RAGState
from app.services.rag.llm import get_groq_llm
from app.services.rag.prompts import DOCUMENT_GRADER_SYSTEM_PROMPT

async def grade_single_doc(llm, query: str, doc: Dict[str, Any], idx: int) -> tuple:
    """Helper to grade an individual document chunk asynchronously."""
    prompt = f"User Query: {query}\n\nDocument Chunk Content:\n{doc['text_content']}"
    try:
        response = await llm.ainvoke([
            SystemMessage(content=DOCUMENT_GRADER_SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])
        content = response.content.strip()

        is_relevant = True
        if "{" in content and "}" in content:
            json_str = content[content.find("{"):content.rfind("}")+1]
            data = json.loads(json_str)
            is_relevant = data.get("is_relevant", True)
        else:
            is_relevant = "true" in content.lower()

        logger.info(f"[GraderNode] Chunk #{idx+1} ({doc['filename']}) -> {'RELEVANT' if is_relevant else 'IRRELEVANT'}")
        return doc, is_relevant
    except Exception as e:
        logger.warning(f"[GraderNode] Grading error for chunk #{idx+1}: {e}. Retaining chunk safely.")
        return doc, True

async def grader_node(state: RAGState) -> dict:
    """
    Evaluates retrieved chunks concurrently using asyncio.gather and ainvoke.
    """
    documents = state.get("documents", [])
    query = state.get("rewritten_query") or state.get("question", "")

    if not documents:
        logger.info("[GraderNode] No documents to grade.")
        return {"documents": [], "relevance_score": 0.0}

    logger.info(f"[GraderNode] Concurrently grading {len(documents)} candidate chunks against query...")

    llm = get_groq_llm(temperature=0.2)
    
    # Grade all chunks in parallel
    tasks = [grade_single_doc(llm, query, doc, idx) for idx, doc in enumerate(documents)]
    graded_results = await asyncio.gather(*tasks)

    relevant_docs = [doc for doc, is_rel in graded_results if is_rel]
    relevance_score = len(relevant_docs) / len(documents) if documents else 0.0

    logger.info(f"[GraderNode] Parallel grading complete: {len(relevant_docs)}/{len(documents)} chunks retained (Score: {relevance_score*100:.1f}%)")
    return {"documents": relevant_docs, "relevance_score": round(relevance_score, 3)}
