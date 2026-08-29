import json
import asyncio
from typing import List, Dict, Any
import requests
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.rag_state import RAGState
from app.core.config import settings
from app.services.rag.llm import get_groq_llm

LISTWISE_RERANK_PROMPT = """You are an expert information retrieval and cross-attention reranker.
You will be given a user query and a list of numbered candidate document excerpts.

Your task:
1. Carefully analyze each candidate excerpt against the user query.
2. Rank the candidates by semantic relevance to the query.
3. Return the indices of the TOP 5 most relevant excerpts in descending order of relevance.

Respond with ONLY a JSON object formatted as:
{
  "top_indices": [index1, index2, index3, index4, index5],
  "reasoning": "Brief justification"
}"""

async def rerank_with_hf(query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calls Hugging Face Inference API for cross-encoder scoring dynamically.
    """
    model_name = settings.HUGGINGFACE_RERANKER_MODEL
    api_url = f"https://api-inference.huggingface.co/models/{model_name}"
    headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"}
    
    # Pair query with each chunk's text content (truncated to 1000 chars for API performance)
    sentences = [doc.get("text_content", "")[:1000] for doc in documents]
    payload = {
        "inputs": {
            "source_sentence": query,
            "sentences": sentences
        }
    }

    loop = asyncio.get_running_loop()
    def _post():
        return requests.post(api_url, headers=headers, json=payload, timeout=2.0)

    response = await loop.run_in_executor(None, _post)
    if response.status_code == 200:
        scores = response.json()
        if isinstance(scores, list) and len(scores) == len(documents):
            scored_docs = []
            for i, doc in enumerate(documents):
                doc_copy = dict(doc)
                score = float(scores[i]) if isinstance(scores[i], (int, float)) else float(scores[i].get("score", 0.0))
                doc_copy["rerank_score"] = round(score, 4)
                doc_copy["original_rank"] = i + 1
                scored_docs.append(doc_copy)
            
            scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
            return scored_docs
            
    raise RuntimeError(f"HF Reranker API returned status {response.status_code}: {response.text}")


async def rerank_with_groq_fallback(query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fast, resilient listwise LLM reranker using Groq when Hugging Face API is unavailable.
    Limits to top 10 candidates to strictly avoid Groq's 8,000 TPM rate limits (429).
    """
    logger.info("[RerankerNode] Executing Groq Flash Listwise Reranker fallback...")
    
    # Filter to top 10 candidates for the LLM call to save tokens and prevent 429
    candidate_docs = documents[:10]
    
    candidates_text = []
    for i, doc in enumerate(candidate_docs):
        fn = doc.get("filename", "")
        pg = doc.get("page_number", "N/A")
        snippet = doc.get("text_content", "")[:200].replace("\n", " ").strip()
        candidates_text.append(f"[{i}] File: {fn} (Page {pg}) -> {snippet}...")

    prompt = (
        f"User Query: {query}\n\n"
        f"Candidate Excerpts:\n" + "\n".join(candidates_text)
    )

    llm = get_groq_llm(temperature=0.3)
    response = await llm.ainvoke([
        SystemMessage(content=LISTWISE_RERANK_PROMPT),
        HumanMessage(content=prompt)
    ])

    content = response.content.strip()
    reranked = []
    seen = set()
    
    if "{" in content and "}" in content:
        data = json.loads(content[content.find("{"):content.rfind("}")+1])
        top_indices = data.get("top_indices", [])
        
        for rank, idx in enumerate(top_indices):
            if isinstance(idx, int) and 0 <= idx < len(candidate_docs) and idx not in seen:
                doc_copy = dict(candidate_docs[idx])
                doc_copy["original_rank"] = idx + 1
                doc_copy["rerank_score"] = round(1.0 - (rank * 0.05), 4)
                reranked.append(doc_copy)
                seen.add(idx)

    # Append any remaining docs from the entire original list to preserve coverage
    for idx, doc in enumerate(documents):
        # If it was in the top 10 but not chosen by LLM, or was in the remaining 10
        is_in_candidate_but_not_chosen = (idx < 10 and idx not in seen)
        is_outside_candidate_pool = (idx >= 10)
        
        if is_in_candidate_but_not_chosen or is_outside_candidate_pool:
            doc_copy = dict(doc)
            doc_copy["original_rank"] = idx + 1
            doc_copy["rerank_score"] = 0.5 - (idx * 0.01) # preserve raw similarity order fallback
            reranked.append(doc_copy)
                
        return reranked

    return documents


async def reranker_node(state: RAGState) -> dict:
    """
    Takes up to 20 candidate chunks from Stage 1 retrieval, applies Cross-Encoder scoring,
    and isolates the top 5 highest-precision chunks.
    """
    documents = state.get("documents", [])
    query = state.get("rewritten_query") or state.get("question", "")
    target_k = 7

    if not documents:
        logger.info("[RerankerNode] No candidate documents to rerank.")
        return {"documents": []}

    logger.info(f"[RerankerNode] Cross-Encoder Reranking {len(documents)} candidate chunks for query: '{query[:60]}...'")

    reranked_docs: List[Dict[str, Any]] = []
    engine_used = settings.HUGGINGFACE_RERANKER_MODEL

    try:
        reranked_docs = await rerank_with_hf(query, documents)
    except Exception as e:
        logger.warning(f"[RerankerNode] Hugging Face cross-encoder failed ({e}). Falling back to Groq listwise reranker.")
        engine_used = "Groq Flash Listwise"
        try:
            reranked_docs = await rerank_with_groq_fallback(query, documents)
        except Exception as fallback_err:
            logger.error(f"[RerankerNode] Both reranking engines failed: {fallback_err}. Using raw vector order.")
            reranked_docs = documents

    final_top_docs = reranked_docs[:target_k]

    # Output structured terminal telemetry
    logger.info(f"╔══════════════════════════════════════════════════════════════════════════════════════════")
    logger.info(f"║ [RerankerNode] RERANKED {len(documents)} CANDIDATES -> TOP {len(final_top_docs)} CHUNKS ISOLATED ({engine_used}):")
    for rank, doc in enumerate(final_top_docs, start=1):
        fn = doc.get("filename", "Unknown")
        pg = doc.get("page_number", "N/A")
        orig_rank = doc.get("original_rank", "N/A")
        score = doc.get("rerank_score", "N/A")
        preview = doc.get("text_content", "")[:120].replace("\n", " ").strip()
        logger.info(f"║ 🎯 Rank #{rank} | ChunkID: {doc.get('chunk_id')} | Page: {pg} | OrigRank: #{orig_rank} | RerankScore: {score}")
        logger.info(f"║    Preview: \"{preview}...\"")
    logger.info(f"╚══════════════════════════════════════════════════════════════════════════════════════════")

    return {"documents": final_top_docs}
