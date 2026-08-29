import re
from typing import Optional
from loguru import logger
from langchain_groq import ChatGroq
from app.core.config import settings
from app.services.rag.prompts import TITLE_GENERATION_PROMPT

def get_groq_llm(temperature: float = 0.2, model_name: Optional[str] = None) -> ChatGroq:
    """
    Returns an initialized ChatGroq LLM instance.
    Uses settings.GROQ_MODEL_NAME (or gpt-oss-20b if specified).
    """
    selected_model = model_name or getattr(settings, "GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
    return ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name=selected_model,
        temperature=temperature
    )

def _clean_title(raw_title: str, question: str) -> str:
    title = raw_title.strip()
    title = re.sub(r'^Title:\s*', '', title, flags=re.IGNORECASE)
    title = title.strip(' "\'`#*')
    if title.endswith("."):
        title = title[:-1].strip()
    if title and len(title) > 2:
        return title
    words = question.strip().split()
    return " ".join(words[:6]) if words else "New Conversation"

async def agenerate_chat_title(question: str, response: str) -> str:
    """
    Asynchronously generates an intelligent 3-to-6 word conversation title using ainvoke.
    """
    try:
        llm = get_groq_llm(temperature=0.2)
        prompt = TITLE_GENERATION_PROMPT.format(
            question=question.strip(),
            response=response[:300].strip()
        )
        result = await llm.ainvoke(prompt)
        raw_title = result.content if hasattr(result, "content") else str(result)
        return _clean_title(raw_title, question)
    except Exception as e:
        logger.warning(f"Async LLM Title generation failed: {e}. Using fallback.")
        words = question.strip().split()
        return " ".join(words[:6]) if words else "New Conversation"

def generate_chat_title(question: str, response: str) -> str:
    """
    Synchronously generates an intelligent 3-to-6 word conversation title.
    """
    try:
        llm = get_groq_llm(temperature=0.2)
        prompt = TITLE_GENERATION_PROMPT.format(
            question=question.strip(),
            response=response[:300].strip()
        )
        result = llm.invoke(prompt)
        raw_title = result.content if hasattr(result, "content") else str(result)
        return _clean_title(raw_title, question)
    except Exception as e:
        logger.warning(f"LLM Title generation failed: {e}. Using fallback.")
        words = question.strip().split()
        return " ".join(words[:6]) if words else "New Conversation"
