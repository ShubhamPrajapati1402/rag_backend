import json
from typing import List, Dict, Any
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.rag_state import RAGState
from app.services.rag.llm import get_groq_llm
from app.services.rag.prompts import BATCH_GRADER_SYSTEM_PROMPT

async def grader_node(state: RAGState) -> dict:
    """
    Evaluates all retrieved chunks in a single batch LLM call to prevent Rate Limits (429)
    and dramatically reduce latency.
    """
    documents = state.get("documents", [])
    query = state.get("rewritten_query") or state.get("question", "")

    if not documents:
        logger.info("[GraderNode] No documents to grade.")
        return {"documents": [], "relevance_score": 0.0}

    logger.info(f"[GraderNode] Grading {len(documents)} candidate chunks in a single batch request...")

    # Format the candidate list
    formatted_chunks = ""
    for idx, doc in enumerate(documents):
        formatted_chunks += f"--- Chunk Index {idx} ---\nSource: {doc.get('filename')} (Page: {doc.get('page_number')})\nContent Excerpt: {doc.get('text_content', '')[:1000]}\n\n"

    prompt = f"User Query: {query}\n\nCandidate Chunks:\n{formatted_chunks}"

    relevant_docs = []
    try:
        llm = get_groq_llm(temperature=0.3)
        response = await llm.ainvoke([
            SystemMessage(content=BATCH_GRADER_SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])
        content = response.content.strip()

        relevant_indices = []
        if "{" in content and "}" in content:
            json_str = content[content.find("{"):content.rfind("}")+1]
            data = json.loads(json_str)
            relevant_indices = data.get("relevant_indices", [])

        # Map indices back to document list
        for idx, doc in enumerate(documents):
            if idx in relevant_indices:
                relevant_docs.append(doc)
                logger.info(f"[GraderNode] Chunk #{idx+1} [ID: {doc.get('chunk_id')}] -> ✅ RELEVANT")
            else:
                logger.info(f"[GraderNode] Chunk #{idx+1} [ID: {doc.get('chunk_id')}] -> ❌ FILTERED OUT")

    except Exception as e:
        logger.warning(f"[GraderNode] Batch grading error: {e}. Falling back to retaining all chunks safely.")
        relevant_docs = documents

    relevance_score = len(relevant_docs) / len(documents) if documents else 0.0
    logger.info(f"[GraderNode] Batch grading complete: {len(relevant_docs)}/{len(documents)} chunks retained (Score: {relevance_score*100:.1f}%)")

    return {"documents": relevant_docs, "relevance_score": round(relevance_score, 3)}
