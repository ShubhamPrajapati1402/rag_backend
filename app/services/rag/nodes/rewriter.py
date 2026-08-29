import json
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.rag_state import RAGState
from app.services.rag.llm import get_groq_llm
from app.services.rag.prompts import QUERY_REWRITER_SYSTEM_PROMPT

async def rewriter_node(state: RAGState) -> dict:
    """
    Rewrites the user query using conversation history and the running summary asynchronously.
    """
    question = state.get("question", "").strip()
    messages = state.get("messages", [])
    summary = state.get("summary", "") or ""
    
    words = question.lower().split()
    pronouns = {"it", "its", "they", "them", "their", "this", "that", "these", "those", "he", "she", "him", "her", "previous", "above"}
    has_pronoun = any(w.strip("?!.,'\"") in pronouns for w in words)

    if (len(messages) <= 1 and not summary) or (not has_pronoun and len(words) >= 4):
        logger.info(f"[RewriterNode] Clean standalone query detected. Retaining directly: '{question}'")
        return {"rewritten_query": question}
        
    logger.info(f"[RewriterNode] Analyzing conversation history and summary for query expansion...")
    
    try:
        llm = get_groq_llm(temperature=0.3)
        
        context_parts = []
        if summary:
            context_parts.append(f"Conversation Summary:\n{summary}")
        if messages:
            recent_history = "\n".join([
                f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
                for m in messages[-4:]
            ])
            context_parts.append(f"Recent Messages:\n{recent_history}")

        full_context = "\n\n".join(context_parts)
        prompt = f"{full_context}\n\nLatest User Message: {question}"
        
        response = await llm.ainvoke([
            SystemMessage(content=QUERY_REWRITER_SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])
        
        content = response.content.strip()
        if "{" in content and "}" in content:
            json_str = content[content.find("{"):content.rfind("}")+1]
            data = json.loads(json_str)
            rewritten = data.get("rewritten_query", question)
        else:
            rewritten = content.strip('"\'')
            
        logger.info(f"[RewriterNode] Query rewritten as: '{rewritten}'")
        return {"rewritten_query": rewritten}
    except Exception as e:
        logger.warning(f"[RewriterNode] Rewriting failed: {e}. Using original question.")
        return {"rewritten_query": question}
