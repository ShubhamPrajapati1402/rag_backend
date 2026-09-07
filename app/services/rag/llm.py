import re
import time
from typing import Optional, Any, Tuple, List, Dict
from loguru import logger
from sqlalchemy.orm import Session

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_google_genai")

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

# Dynamic imports with fallbacks
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None

from app.core.config import settings
from app.core.crypto import decrypt_secret
from app.db.session import SessionLocal
from app.models.user_api_key import UserAPIKey
from app.services.rag.prompts import TITLE_GENERATION_PROMPT

def infer_provider(model_name: Optional[str] = None, api_key: Optional[str] = None) -> str:
    """Auto-detect provider from model name and key prefix."""
    if not model_name:
        return "inbuilt"
    m = str(model_name).lower().strip()
    if m in ("inbuilt", "default", "auto", ""):
        return "inbuilt"
    if m.startswith("gpt-") or m.startswith("o1") or m.startswith("o3") or m.startswith("text-embedding") or "davinci" in m:
        return "openai"
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gemini"):
        return "gemini"
    if "llama" in m or "qwen" in m or "mixtral" in m or "gemma" in m:
        return "groq"
    if "deepseek" in m:
        return "deepseek"
    if "mistral" in m or "codestral" in m:
        return "mistral"
    if api_key:
        k = api_key.strip()
        if k.startswith("sk-ant-"):
            return "anthropic"
        if k.startswith("gsk_"):
            return "groq"
        if k.startswith("AIza"):
            return "gemini"
        if k.startswith("sk-"):
            return "openai"
    return "openai"

def resolve_provider_credentials(
    provider: str,
    explicit_api_key: Optional[str] = None,
    explicit_base_url: Optional[str] = None,
    user_id: Optional[int] = None,
    db: Optional[Session] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolves API Key and Base URL using the hierarchy:
    1. Explicit request parameters (ephemeral override)
    2. Stored encrypted User API Key in PostgreSQL (vault)
    3. System default .env configuration (for inbuilt / gemini / groq)
    """
    prov = (provider or "inbuilt").lower().strip()
    
    # 1. Explicit override passed directly
    if explicit_api_key:
        return explicit_api_key.strip(), explicit_base_url

    # 2. Vault Lookup in DB
    if user_id:
        owns_db = False
        if db is None:
            db = SessionLocal()
            owns_db = True
        try:
            key_record = db.query(UserAPIKey).filter(
                UserAPIKey.user_id == user_id,
                UserAPIKey.provider == prov,
                UserAPIKey.is_active == True
            ).first()

            if key_record and key_record.encrypted_key:
                decrypted = decrypt_secret(key_record.encrypted_key)
                return decrypted, key_record.base_url
        except Exception as e:
            logger.warning(f"[LLMFactory] Failed to retrieve user API key for user_id={user_id}, provider={prov}: {e}")
        finally:
            if owns_db:
                db.close()

    # 3. System Defaults for inbuilt, gemini, groq
    if prov in ("inbuilt", "gemini"):
        return settings.GEMINI_API_KEY, None
    elif prov == "groq":
        return settings.GROQ_API_KEY, None

    return None, explicit_base_url


def get_llm(
    temperature: Any = 0.3,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    user_id: Optional[int] = None,
    db: Optional[Session] = None
) -> Any:
    """
    Universal Dynamic LLM Factory. Instantiates the appropriate LangChain ChatModel
    based on provider, model, and resolved credentials.
    """
    # Robust argument resolution in case provider was passed positionally
    if isinstance(temperature, str):
        if model_provider is None:
            model_provider = temperature
        temp_val = 0.3
    else:
        try:
            temp_val = float(temperature) if temperature is not None else 0.3
        except (ValueError, TypeError):
            temp_val = 0.3

    provider = (model_provider or "inbuilt").lower().strip()
    if provider in ("custom", "auto", "byok", "") or (provider == "inbuilt" and model_name and model_name.lower() not in ("default", "inbuilt", settings.GEMINI_MODEL_NAME.lower())):
        inferred = infer_provider(model_name=model_name, api_key=api_key)
        if inferred != "inbuilt" or not model_name:
            provider = inferred

    resolved_key, resolved_base_url = resolve_provider_credentials(
        provider=provider,
        explicit_api_key=api_key,
        explicit_base_url=base_url,
        user_id=user_id,
        db=db
    )

    # 1. Inbuilt Default Resilient Chain (Gemini Flash + Groq Fallbacks)
    if provider == "inbuilt":
        primary = ChatGoogleGenerativeAI(
            model=model_name or settings.GEMINI_MODEL_NAME,
            google_api_key=resolved_key or settings.GEMINI_API_KEY,
            temperature=temp_val,
            timeout=15.0,
            max_retries=0
        )
        fallback_1 = ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model_name=settings.GROQ_MODEL_NAME,
            temperature=temp_val,
            timeout=15.0,
            max_retries=2
        )
        fallback_2 = ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model_name=settings.GROQ_FALLBACK_MODEL_NAME,
            temperature=temp_val,
            timeout=15.0,
            max_retries=2
        )
        return primary.with_fallbacks([fallback_1, fallback_2])

    # 2. Google Gemini
    if provider == "gemini":
        key = resolved_key or settings.GEMINI_API_KEY
        if not key:
            raise ValueError("Google Gemini API Key is required. Please add your key in settings.")
        return ChatGoogleGenerativeAI(
            model=model_name or settings.GEMINI_MODEL_NAME,
            google_api_key=key,
            temperature=temp_val,
            timeout=25.0
        )

    # 3. Groq
    if provider == "groq":
        key = resolved_key or settings.GROQ_API_KEY
        if not key:
            raise ValueError("Groq API Key is required. Please add your key in settings.")
        return ChatGroq(
            model_name=model_name or settings.GROQ_MODEL_NAME,
            groq_api_key=key,
            temperature=temp_val,
            timeout=25.0
        )

    # 4. OpenAI (GPT-4o, GPT-4o-mini, o1, o3-mini)
    if provider == "openai":
        if ChatOpenAI is None:
            raise ImportError("langchain-openai is not installed. Run 'pip install langchain-openai'.")
        if not resolved_key:
            raise ValueError("OpenAI API Key is required. Please add your OpenAI key in settings.")
        kwargs = {
            "model": model_name or "gpt-4o",
            "api_key": resolved_key,
            "temperature": temp_val,
            "timeout": 30.0
        }
        if resolved_base_url:
            kwargs["base_url"] = resolved_base_url
        return ChatOpenAI(**kwargs)

    # 5. Anthropic Claude (Claude 3.5 Sonnet / Haiku)
    if provider == "anthropic":
        if ChatAnthropic is None:
            raise ImportError("langchain-anthropic is not installed. Run 'pip install langchain-anthropic'.")
        if not resolved_key:
            raise ValueError("Anthropic API Key is required. Please add your Anthropic key in settings.")
        return ChatAnthropic(
            model=model_name or "claude-3-5-sonnet-latest",
            api_key=resolved_key,
            temperature=temp_val,
            timeout=30.0
        )

    # 6. DeepSeek, Mistral, OpenRouter / OpenAI-Compatible
    if provider in ("deepseek", "mistral", "openrouter", "openai_compatible"):
        if ChatOpenAI is None:
            raise ImportError("langchain-openai is required for OpenAI-compatible providers.")
        
        target_base_url = resolved_base_url
        if not target_base_url:
            if provider == "deepseek":
                target_base_url = "https://api.deepseek.com/v1"
            elif provider == "mistral":
                target_base_url = "https://api.mistral.ai/v1"
            elif provider == "openrouter":
                target_base_url = "https://openrouter.ai/api/v1"

        if not resolved_key:
            raise ValueError(f"{provider.capitalize()} API Key is required. Please provide an API key.")

        kwargs = {
            "model": model_name or "gpt-4o",
            "api_key": resolved_key,
            "temperature": temp_val,
            "timeout": 30.0
        }
        if target_base_url:
            kwargs["base_url"] = target_base_url
        return ChatOpenAI(**kwargs)

    # Default fallback to inbuilt
    logger.warning(f"[LLMFactory] Unknown provider '{provider}', falling back to inbuilt chain.")
    return get_llm(temperature=temp_val, model_provider="inbuilt")


def get_groq_llm(
    temperature: float = 0.3,
    model_name: Optional[str] = None,
    model_provider: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    user_id: Optional[int] = None
) -> Any:
    """
    Universal proxy returning the appropriate LLM instance with provider support.
    """
    return get_llm(
        temperature=temperature,
        model_provider=model_provider,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        user_id=user_id
    )


async def validate_model_connection(
    provider: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model_name: Optional[str] = None,
    user_id: Optional[int] = None
) -> Tuple[bool, str, float]:
    """
    Validates credentials by performing a fast 1-token diagnostic call.
    Returns (success, message, latency_ms).
    """
    start_time = time.time()
    try:
        llm = get_llm(
            temperature=0.0,
            model_provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            user_id=user_id
        )
        response = await llm.ainvoke([HumanMessage(content="Hello, answer with 'Connection verified.'")])
        latency = round((time.time() - start_time) * 1000, 2)
        content = extract_text_content(response.content)
        return True, f"Connection verified successfully in {latency}ms.", latency
    except Exception as e:
        latency = round((time.time() - start_time) * 1000, 2)
        logger.warning(f"[LLMFactory] Connection test failed for provider '{provider}': {e}")
        return False, str(e), latency


def extract_text_content(content: Any) -> str:
    """
    Safely extracts string content from both raw strings and structured message part lists.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join([
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        ])
    return str(content)


def _clean_title(raw_title: str, question: str) -> str:
    title = extract_text_content(raw_title).strip()
    title = re.sub(r'^Title:\s*', '', title, flags=re.IGNORECASE)
    title = title.strip(' "\'`#*')
    if title.endswith("."):
        title = title[:-1].strip()
    if title and len(title) > 2:
        return title
    words = question.strip().split()
    return " ".join(words[:10]) if words else "New Conversation"


async def agenerate_chat_title(
    question: str,
    response: str,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    user_id: Optional[int] = None
) -> str:
    """
    Asynchronously generates an intelligent conversation title using ainvoke.
    """
    try:
        llm = get_llm(
            temperature=0.3,
            model_provider=model_provider or "inbuilt",
            model_name=model_name,
            api_key=api_key,
            user_id=user_id
        )
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


def generate_chat_title(
    question: str,
    response: str,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    user_id: Optional[int] = None
) -> str:
    """
    Synchronously generates an intelligent conversation title.
    """
    try:
        llm = get_llm(
            temperature=0.3,
            model_provider=model_provider or "inbuilt",
            model_name=model_name,
            api_key=api_key,
            user_id=user_id
        )
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
