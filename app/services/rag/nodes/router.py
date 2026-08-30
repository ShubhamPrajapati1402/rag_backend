import json
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.rag_state import RAGState
from app.services.rag.llm import get_groq_llm
from app.services.rag.prompts import ROUTER_SYSTEM_PROMPT

async def router_node(state: RAGState) -> dict:
    """
    Evaluates the user question to determine whether document retrieval is required asynchronously.
    """
    question = state.get("question", "").strip()
    messages = state.get("messages", [])
    summary = state.get("summary", "") or ""
    
    logger.info(f"[RouterNode] Evaluating route for question: '{question[:60]}...'")
    
    # Fast heuristic check for simple standalone greetings
    lower_q = question.lower().strip("?!. ")
    if lower_q in ("hi", "hello", "hey", "good morning", "good evening", "who are you", "what can you do", "help") and not summary:
        logger.info(f"[RouterNode] Heuristic detected greeting -> direct")
        return {"route": "direct"}

    try:
        llm = get_groq_llm(temperature=0.3)
        
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
        
        content = response.content.strip()
        if "{" in content and "}" in content:
            json_str = content[content.find("{"):content.rfind("}")+1]
            data = json.loads(json_str)
            route = data.get("route", "vectorstore")
        else:
            route = "vectorstore" if ("vectorstore" in content.lower() or "document" in content.lower()) else "direct"
            
        logger.info(f"[RouterNode] Route determined: {route.upper()}")
        return {"route": route}
    except Exception as e:
        logger.warning(f"[RouterNode] Classification failed: {e}. Defaulting to 'vectorstore'")
        return {"route": "vectorstore"}
