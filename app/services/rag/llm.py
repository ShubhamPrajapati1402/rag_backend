import re
from typing import Optional, Any
from loguru import logger
from langchain_groq import ChatGroq
from app.core.config import settings
from app.services.rag.prompts import TITLE_GENERATION_PROMPT

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

def get_llm(temperature: float = 0.3) -> Any:
    """
    Returns a unified LLM instance using Google Gemini 2.5 Flash as the primary engine
    and Groq Llama 20b as fallback, enforcing a temperature of 0.3.
    """
    primary = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL_NAME,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temperature
    )
    fallback = ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name=settings.GROQ_MODEL_NAME,
        temperature=temperature
    )
    return primary.with_fallbacks([fallback])

def get_groq_llm(temperature: float = 0.3, model_name: Optional[str] = None) -> Any:
    """
    Upgraded proxy return that defaults to Google Gemini with Groq fallback.
    """
    return get_llm(temperature=temperature)

def _clean_title(raw_title: str, question: str) -> str:
    title = raw_title.strip()
    title = re.sub(r'^Title:\s*', '', title, flags=re.IGNORECASE)
    title = title.strip(' "\'`#*')
    if title.endswith("."):
        title = title[:-1].strip()
    if title and len(title) > 2:
        return title
    words = question.strip().split()
    return " ".join(words[:10]) if words else "New Conversation"

async def agenerate_chat_title(question: str, response: str) -> str:
    """
    Asynchronously generates an intelligent conversation title using ainvoke.
    """
    try:
        llm = get_groq_llm(temperature=0.3)
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
        return " ".join(words[:10]) if words else "New Conversation"

def generate_chat_title(question: str, response: str) -> str:
    """
    Synchronously generates an intelligent conversation title.
    """
    try:
        llm = get_groq_llm(temperature=0.3)
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
        return " ".join(words[:10]) if words else "New Conversation"
