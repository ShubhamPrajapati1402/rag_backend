from typing import List, Dict, Any
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.rag_state import RAGState, Citation
from app.services.rag.llm import get_groq_llm
from app.services.rag.prompts import (
    GENERATOR_SYSTEM_PROMPT,
    DIRECT_GENERATOR_SYSTEM_PROMPT
)

async def rag_generator_node(state: RAGState) -> dict:
    """
    Synthesizes the grounded answer using relevant document chunks asynchronously.
    """
    question = state.get("question", "")
    documents = state.get("documents", [])

    logger.info(f"[RAGGeneratorNode] Generating grounded response using {len(documents)} context chunks...")

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

    llm = get_groq_llm(temperature=0.2)
    response = await llm.ainvoke([
        SystemMessage(content=GENERATOR_SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ])

    answer = response.content.strip()
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

    llm = get_groq_llm(temperature=0.2)
    response = await llm.ainvoke([
        SystemMessage(content=DIRECT_GENERATOR_SYSTEM_PROMPT),
        HumanMessage(content=f"{history_text}User: {question}")
    ])

    return {"generation": response.content.strip(), "citations": []}


async def fallback_generator_node(state: RAGState) -> dict:
    """
    Produces a transparent, grounded reply when no relevant chunks are found in the documents.
    """
    question = state.get("question", "")
    logger.info(f"[FallbackGeneratorNode] No relevant documents found for query.")

    message = (
        f"Based on the uploaded documents in your workspace, I could not find information regarding "
        f"**\"{question}\"**.\n\n"
        f"Please verify that the relevant document (PDF, spreadsheet, DOCX, etc.) has been uploaded and ingested, "
        f"or try rephrasing your inquiry with specific terms."
    )
    return {"generation": message, "citations": []}
