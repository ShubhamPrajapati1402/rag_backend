from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.rag_state import RAGState
from app.services.rag.llm import get_groq_llm
from app.services.rag.prompts import SUMMARIZER_SYSTEM_PROMPT

async def summarizer_node(state: RAGState) -> dict:
    """
    Progressively condenses conversation history into a running cumulative summary asynchronously.
    """
    messages = state.get("messages", [])
    existing_summary = state.get("summary", "") or ""

    if len(messages) < 6 or (existing_summary and len(messages) % 4 != 0):
        return {"summary": existing_summary}

    logger.info(f"[SummarizerNode] Periodically updating cumulative conversation summary ({len(messages)} messages)...")

    try:
        llm = get_groq_llm(temperature=0.3)
        formatted_messages = "\n".join([
            f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
            for m in messages
        ])

        prompt = (
            f"Existing Summary:\n{existing_summary if existing_summary else 'None (New Conversation)'}\n\n"
            f"Full Conversation History:\n{formatted_messages}\n\n"
            f"Updated Cumulative Summary:"
        )

        response = await llm.ainvoke([
            SystemMessage(content=SUMMARIZER_SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])

        new_summary = response.content.strip()
        logger.info(f"[SummarizerNode] Progressive summary updated ({len(new_summary)} chars).")
        return {"summary": new_summary}
    except Exception as e:
        logger.warning(f"[SummarizerNode] Summarization failed: {e}. Preserving existing summary.")
        return {"summary": existing_summary}
