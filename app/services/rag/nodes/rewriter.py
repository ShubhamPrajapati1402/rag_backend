import json
from typing import List, Dict, Any, Optional
from loguru import logger
from sqlalchemy import select
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas.rag_state import RAGState
from app.services.rag.llm import get_groq_llm, extract_text_content
from app.services.rag.prompts import QUERY_REWRITER_SYSTEM_PROMPT
from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus

async def rewriter_node(state: RAGState) -> dict:
    """
    Rewrites the user query using conversation history and the running summary asynchronously.
    Intelligently identifies target document IDs (ChatGPT-style auto-scoping) if not manually selected.
    """
    question = state.get("question", "").strip()
    messages = state.get("messages", [])
    summary = state.get("summary", "") or ""
    existing_doc_ids = state.get("document_ids")
    user_id = state.get("user_id")

    words = question.lower().split()
    pronouns = {"it", "its", "they", "them", "their", "this", "that", "these", "those", "he", "she", "him", "her", "previous", "above"}
    has_pronoun = any(w.strip("?!.,'\"") in pronouns for w in words)

    # Fast 0ms path: If document is already manually selected AND query has no pronouns, bypass LLM rewriter
    if existing_doc_ids and len(existing_doc_ids) > 0 and (not has_pronoun or len(words) >= 5):
        logger.info(f"[RewriterNode] Manual document selection active ({existing_doc_ids}). Fast 0ms pass-through: '{question}'")
        return {"rewritten_query": question}

    # If standalone query with no prior messages or pronouns, pass through in 0ms
    if (len(messages) <= 1 and not summary and not has_pronoun and len(words) >= 3 and existing_doc_ids):
        logger.info(f"[RewriterNode] Standalone query detected. Fast 0ms pass-through: '{question}'")
        return {"rewritten_query": question}

    # Fetch active user documents from DB for intelligent auto-scoping
    db = SessionLocal()
    try:
        query = select(Document.id, Document.filename).where(
            Document.status == DocumentStatus.COMPLETED
        )
        if user_id:
            query = query.where((Document.user_id == user_id) | (Document.user_id.is_(None)))
        docs_result = db.execute(query).fetchall()
        doc_map = {row.id: row.filename for row in docs_result}
        
        if len(doc_map) > 1:
            doc_lines = [f"- [ID: {doc_id}] \"{filename}\"" for doc_id, filename in doc_map.items()]
            available_docs_text = "Available User Documents:\n" + "\n".join(doc_lines)
        else:
            available_docs_text = ""
            doc_map = {}
    except Exception as db_err:
        logger.warning(f"[RewriterNode] Failed to fetch active documents for auto-scoping: {db_err}")
        available_docs_text = ""
        doc_map = {}
    finally:
        db.close()

    try:
        llm = get_groq_llm(
            temperature=0.1,
            model_provider="groq",
            model_name=None,  # Uses fast default Groq model (openai/gpt-oss-120b)
            api_key=state.get("custom_api_key"),
            base_url=state.get("custom_base_url"),
            user_id=state.get("user_id")
        )
        
        context_parts = []
        if available_docs_text:
            context_parts.append(available_docs_text)
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
        
        content = extract_text_content(response.content).strip()
        rewritten = question
        inferred_doc_ids: Optional[List[int]] = None
        
        if "{" in content and "}" in content:
            try:
                json_str = content[content.find("{"):content.rfind("}")+1]
                data = json.loads(json_str)
                rewritten = data.get("rewritten_query", question) or question
                raw_ids = data.get("target_document_ids", [])
                if isinstance(raw_ids, list) and len(raw_ids) > 0:
                    valid_ids = [int(i) for i in raw_ids if isinstance(i, (int, str)) and int(i) in doc_map]
                    if valid_ids:
                        inferred_doc_ids = valid_ids
                        matched_names = [doc_map[i] for i in valid_ids]
                        logger.info(f"[RewriterNode] Auto-scoped query to document(s): {matched_names} (IDs: {valid_ids})")
            except Exception as parse_err:
                logger.debug(f"[RewriterNode] JSON parse fallback: {parse_err}")
                rewritten = content.strip('"\'')
        else:
            rewritten = content.strip('"\'')
            
        logger.info(f"[RewriterNode] Query rewritten as: '{rewritten}'")
        result = {"rewritten_query": rewritten}
        if inferred_doc_ids and not existing_doc_ids:
            result["document_ids"] = inferred_doc_ids
        return result

    except Exception as e:
        logger.warning(f"[RewriterNode] Rewriting failed: {e}. Using original question.")
        return {"rewritten_query": question}

