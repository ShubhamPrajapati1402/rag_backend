import re
import json
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.rag_state import RAGState
from app.services.rag.llm import get_groq_llm, extract_text_content
from app.services.rag.prompts import ROUTER_SYSTEM_PROMPT
from app.core.config import settings

async def router_node(state: RAGState) -> dict:
    """
    Evaluates the user question to determine whether document retrieval is required asynchronously.
    Executes in 0ms for document-scoped queries or conversational greetings, and <1s on Groq LPU otherwise.
    """
    question = state.get("question", "").strip()
    messages = state.get("messages", [])
    summary = state.get("summary", "") or ""
    document_ids = state.get("document_ids")
    
    logger.info(f"[RouterNode] Evaluating route for question: '{question[:60]}...'")
    
    # 1. Fast regex heuristic check for simple standalone greetings / conversational pleasantries (0ms)
    lower_q = question.lower().strip("?!.,'\" ")
    is_greeting = bool(re.match(
        r'^(h+i+|h+e+y+|hello+|hola|sup|yo|howdy|greetings|good\s+(morning|afternoon|evening|night)|who\s+are\s+you|what\s+can\s+you\s+do|help|thanks?|thank\s+you|bye|goodbye)$',
        lower_q
    ))
    if is_greeting and not summary and len(messages) <= 1:
        logger.info(f"[RouterNode] Conversational greeting detected '{question}' -> DIRECT (0ms)")
        return {"route": "direct"}

    # 2. Document-scoped session fast-path (0ms):
    # If the user has active selected document(s) in this session and it's not a greeting,
    # route directly to vectorstore without querying any LLM.
    if document_ids and len(document_ids) > 0:
        logger.info(f"[RouterNode] Active document context ({document_ids}). Routing to VECTORSTORE (0ms)")
        return {"route": "vectorstore"}

    # 3. For general queries without specific document selection, evaluate route via ultra-fast Groq LPU (<1s)
    try:
        llm = get_groq_llm(
            temperature=0.1,
            model_name=settings.GROQ_FALLBACK_MODEL_NAME or "openai/gpt-oss-20b"
        )
        
        context_parts = []
        if summary:
            context_parts.append(f"Conversation Summary:\n{summary}")
        if messages:
            recent_turns = "\n".join([f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in messages[-4:]])
            context_parts.append(f"Recent Messages:\n{recent_turns}")
            
        context_preview = "\n\n".join(context_parts)
        prompt = f"{context_preview}\n\nLatest Question: {question}"
        
        response = await llm.ainvoke([
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])
        
        content = extract_text_content(response.content).strip()
        if "{" in content and "}" in content:
            json_str = content[content.find("{"):content.rfind("}")+1]
            data = json.loads(json_str)
            route = data.get("route", "vectorstore")
        else:
            route = "vectorstore" if ("vectorstore" in content.lower() or "document" in content.lower()) else "direct"
            
        logger.info(f"[RouterNode] Groq LPU route determined: {route.upper()}")
        return {"route": route}
    except Exception as e:
        logger.warning(f"[RouterNode] Classification failed: {e}. Defaulting to 'vectorstore'")
        return {"route": "vectorstore"}
