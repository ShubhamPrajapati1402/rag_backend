import re
from typing import List, Dict, Any
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.rag_state import RAGState, Citation
from app.services.rag.llm import get_llm, extract_text_content
from app.services.rag.prompts import (
    GENERATOR_SYSTEM_PROMPT,
    DIRECT_GENERATOR_SYSTEM_PROMPT,
    FALLBACK_REFUSAL_SYSTEM_PROMPT
)

async def rag_generator_node(state: RAGState) -> dict:
    """
    Synthesizes the grounded answer using relevant document chunks asynchronously.
    """
    question = state.get("question", "")
    documents = state.get("documents", [])

    logger.info(f"╔══════════════════════════════════════════════════════════════════════════════════════════")
    logger.info(f"║ [RAGGeneratorNode] SELECTED CHUNKS FOR ANSWER GENERATION ({len(documents)} Chunks Total):")
    for i, doc in enumerate(documents):
        fn = doc.get("filename", "Unknown Document")
        pg = doc.get("page_number") or "N/A"
        sheet = doc.get("sheet_name") or "N/A"
        chunk_idx = doc.get("chunk_index", i)
        sim = doc.get("similarity_score", "N/A")
        chunk_id = doc.get("chunk_id", "N/A")
        preview = doc.get("text_content", "")[:130].replace("\n", " ").strip()
        logger.info(f"║ 📄 Chunk [{i+1}] | ChunkID: {chunk_id} | File: {fn} | Page: {pg} | Similarity: {sim}")
        logger.info(f"║    Excerpt: \"{preview}...\"")
    logger.info(f"╚══════════════════════════════════════════════════════════════════════════════════════════")

    context_blocks = []
    citations: List[Dict[str, Any]] = []

    for i, doc in enumerate(documents):
        fn = doc.get("filename", "Unknown Document")
        pg = doc.get("page_number")
        sheet = doc.get("sheet_name")
        chunk_idx = doc.get("chunk_index", i)

        loc_parts = [f"File: {fn}"]
        if pg:
            loc_parts.append(f"Page: {pg}")
        if sheet:
            loc_parts.append(f"Sheet: {sheet}")
        loc_str = ", ".join(loc_parts)

        context_blocks.append(f"--- Document Source [{i+1}] ({loc_str}) ---\n{doc['text_content']}")

        preview = doc["text_content"][:150].replace("\n", " ").strip() + "..."
        citations.append({
            "document_id": doc.get("document_id"),
            "filename": fn,
            "page_number": pg,
            "sheet_name": sheet,
            "chunk_index": chunk_idx,
            "text_preview": preview
        })

    context_text = "\n\n".join(context_blocks)
    prompt = f"Context Information:\n{context_text}\n\nUser Question:\n{question}\n\nAnswer:"

    llm = get_llm(
        temperature=state.get("temperature", 0.3) or 0.3,
        model_provider=state.get("model_provider"),
        model_name=state.get("model_name"),
        api_key=state.get("custom_api_key"),
        base_url=state.get("custom_base_url"),
        user_id=state.get("user_id")
    )
    response = await llm.ainvoke([
        SystemMessage(content=GENERATOR_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])

    answer = extract_text_content(response.content).strip()
    # Clean up duplicate markdown URLs like [https://url](https://url)
    answer = re.sub(r'\[(https?://[^\s\]]+)\]\(\1\)', r'\1', answer)
    answer = re.sub(r'\[((?:www\.)?[^\s\]]+)\]\((?:https?://)?\1\)', r'https://\1', answer)
    # Ensure Markdown table rows have proper line breaks if squashed
    answer = re.sub(r'\|\s*\|(?=[-\s\w*#])', '|\n|', answer)
    return {"generation": answer, "citations": citations}


async def direct_generator_node(state: RAGState) -> dict:
    """
    Generates direct responses for conversational greetings asynchronously.
    """
    question = state.get("question", "")
    messages = state.get("messages", [])
    summary = state.get("summary", "") or ""
    logger.info(f"[DirectGeneratorNode] Generating direct conversation response...")

    history_text = ""
    if summary:
        history_text += f"Conversation Summary:\n{summary}\n\n"
    if len(messages) > 1:
        history_text += "Recent Conversation:\n" + "\n".join([
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in messages[-4:]
        ]) + "\n\n"

    llm = get_llm(
        temperature=state.get("temperature", 0.3) or 0.3,
        model_provider=state.get("model_provider"),
        model_name=state.get("model_name"),
        api_key=state.get("custom_api_key"),
        base_url=state.get("custom_base_url"),
        user_id=state.get("user_id")
    )
    response = await llm.ainvoke([
        SystemMessage(content=DIRECT_GENERATOR_SYSTEM_PROMPT),
        HumanMessage(content=f"{history_text}User: {question}")
    ])

    return {"generation": extract_text_content(response.content).strip(), "citations": []}


async def fallback_generator_node(state: RAGState) -> dict:
    """
    Produces a dynamic, context-aware polite refusal when no relevant chunks are found in the documents.
    """
    question = state.get("question", "")
    logger.info(f"[FallbackGeneratorNode] Generating dynamic polite refusal for query: '{question}'...")

    llm = get_llm(
        temperature=state.get("temperature", 0.3) or 0.3,
        model_provider=state.get("model_provider"),
        model_name=state.get("model_name"),
        api_key=state.get("custom_api_key"),
        base_url=state.get("custom_base_url"),
        user_id=state.get("user_id")
    )
    response = await llm.ainvoke([
        SystemMessage(content=FALLBACK_REFUSAL_SYSTEM_PROMPT),
        HumanMessage(content=f"User Question: {question}")
    ])

    return {"generation": extract_text_content(response.content).strip(), "citations": []}
