import json
import asyncio
from typing import List, Optional, AsyncGenerator
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger

from app.db.session import get_db, SessionLocal
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.api.deps import get_current_user
from app.schemas.chat_schemas import (
    ChatRequest,
    ChatResponse,
    ChatSessionSummary,
    ChatSessionDetail,
    ChatMessageItem,
    CitationSchema
)
from app.services.rag.graph import rag_agent_app
from app.services.rag.llm import generate_chat_title, agenerate_chat_title

router = APIRouter(prefix="/chat", tags=["Agentic RAG Chat"])

def format_sse(event: str, data: dict) -> str:
    """Helper to format Server-Sent Event payload."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream", summary="Stream RAG Agent responses using Server-Sent Events (SSE)")
async def stream_chat_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Executes the Stateful LangGraph RAG Agent with real-time token streaming and
    agent node status telemetry via Server-Sent Events (SSE).
    """
    user_id = current_user.id
    
    # 1. Initialize or load ChatSession
    db = SessionLocal()
    try:
        is_new_session = False
        if request.session_id:
            session = db.query(ChatSession).filter(
                ChatSession.id == request.session_id,
                ChatSession.user_id == user_id
            ).first()
            if not session:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
        else:
            is_new_session = True
            session = ChatSession(user_id=user_id, title="New Conversation")
            db.add(session)
            db.commit()
            db.refresh(session)

        session_id = session.id
        initial_title = session.title

        # Load recent message history
        past_messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()

        formatted_history = [
            {"role": m.role, "content": m.content}
            for m in past_messages[-10:]
        ]
    finally:
        db.close()

    # Initial state
    initial_state = {
        "messages": formatted_history + [{"role": "user", "content": request.question}],
        "summary": "",
        "question": request.question,
        "rewritten_query": "",
        "documents": [],
        "route": "vectorstore",
        "generation": "",
        "citations": [],
        "relevance_score": 1.0,
        "session_id": session_id,
        "user_id": user_id,
        "document_ids": request.document_ids
    }

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send initial metadata
        yield format_sse("metadata", {
            "session_id": session_id,
            "title": initial_title,
            "is_new_session": is_new_session
        })

        accumulated_text = ""
        final_citations = []
        route_taken = "vectorstore"
        final_state = {}

        try:
            # Stream LangGraph execution events
            async for event in rag_agent_app.astream_events(initial_state, version="v2"):
                kind = event.get("event")
                name = event.get("name", "")

                # Node execution lifecycle events with live layman thoughts
                if kind == "on_chain_start" and name in (
                    "summarizer", "input_guardrail", "router", "rewriter", "retriever", "grader",
                    "rag_generator", "hallucination_guard", "direct_generator", "fallback_generator"
                ):
                    thought_map = {
                        "summarizer": "Recalling key topics from your conversation history...",
                        "input_guardrail": "Validating request against security and safety guardrails...",
                        "router": "Analyzing question intent to choose best knowledge path...",
                        "rewriter": "Refining search terms and resolving conversation context...",
                        "retriever": "Searching vector database for high-similarity document excerpts...",
                        "grader": "Evaluating retrieved excerpts for factual relevance...",
                        "rag_generator": "Formulating grounded answer with verified citations...",
                        "hallucination_guard": "Auditing answer groundedness against source documents...",
                        "direct_generator": "Formulating direct conversational response...",
                        "fallback_generator": "Checking document coverage..."
                    }
                    thought = thought_map.get(name, f"Executing {name}...")

                    yield format_sse("trace", {
                        "step": name,
                        "status": "active",
                        "thought": thought
                    })
                    yield format_sse("node_status", {"node": name, "status": "started"})

                elif kind == "on_chain_end" and name in (
                    "summarizer", "input_guardrail", "router", "rewriter", "retriever", "grader",
                    "rag_generator", "hallucination_guard", "direct_generator", "fallback_generator"
                ):
                    output_data = event.get("data", {}).get("output", {})
                    end_thought = "Completed step."

                    if isinstance(output_data, dict):
                        if "route" in output_data:
                            route_taken = output_data["route"]
                            if route_taken == "blocked":
                                end_thought = "Security check: Request flagged by policy."
                            else:
                                end_thought = f"Strategy chosen: {'Document Knowledge Search' if route_taken == 'vectorstore' else 'Direct Conversation'}"
                        if "citations" in output_data:
                            final_citations = output_data["citations"]
                        if "rewritten_query" in output_data and name == "rewriter":
                            end_thought = f"Optimized search query: \"{output_data['rewritten_query']}\""
                        if "documents" in output_data and name == "retriever":
                            end_thought = f"Found {len(output_data['documents'])} candidate excerpts from documents."
                        if "documents" in output_data and name == "grader":
                            score = int(output_data.get("relevance_score", 1.0) * 100)
                            end_thought = f"Verified {len(output_data['documents'])} relevant excerpts (Relevance Score: {score}%)."
                        if name == "hallucination_guard":
                            end_thought = "Groundedness verified: 100% faithful to source document context."
                        if name in ("rag_generator", "direct_generator"):
                            end_thought = "Answer generated and verified against source documents."

                    yield format_sse("trace", {
                        "step": name,
                        "status": "done",
                        "thought": end_thought
                    })
                    yield format_sse("node_status", {
                        "node": name,
                        "status": "completed",
                        "route": route_taken
                    })

                # Streaming LLM tokens ONLY from generator nodes (ignore internal router/summarizer/grader LLM streams)
                elif kind == "on_chat_model_stream":
                    current_node = event.get("metadata", {}).get("langgraph_node", "")
                    if current_node in ("rag_generator", "direct_generator", "fallback_generator"):
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            token = chunk.content
                            accumulated_text += token
                            yield format_sse("token", {"text": token})

            # Send citations if document context was used
            if final_citations:
                yield format_sse("citations", {"citations": final_citations})

            # Persist the full conversation turn to PostgreSQL
            persist_db = SessionLocal()
            try:
                db_session = persist_db.query(ChatSession).filter(ChatSession.id == session_id).first()
                
                user_msg = ChatMessage(
                    session_id=session_id,
                    role="user",
                    content=request.question
                )
                assistant_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=accumulated_text,
                    citations=final_citations,
                    route_taken=route_taken
                )
                persist_db.add_all([user_msg, assistant_msg])

                # Update title if new session
                final_title = db_session.title if db_session else initial_title
                if is_new_session or (db_session and db_session.title == "New Conversation"):
                    final_title = await agenerate_chat_title(request.question, accumulated_text)
                    if db_session:
                        db_session.title = final_title

                if db_session:
                    db_session.updated_at = datetime.now(ZoneInfo("Asia/Kolkata"))
                persist_db.commit()
            finally:
                persist_db.close()

            # Emit completion event
            yield format_sse("done", {
                "session_id": session_id,
                "title": final_title,
                "route_taken": route_taken,
                "total_chars": len(accumulated_text)
            })

        except Exception as e:
            logger.error(f"[SSEStream] Stream execution error: {e}")
            yield format_sse("error", {"error": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("", response_model=ChatResponse, summary="Send message to RAG Agent (Synchronous JSON)")
async def send_chat_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Synchronous fallback endpoint executing the Stateful LangGraph RAG Agent on the user question.
    """
    user_id = current_user.id
    
    is_new_session = False
    if request.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == request.session_id,
            ChatSession.user_id == user_id
        ).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    else:
        is_new_session = True
        session = ChatSession(user_id=user_id, title="New Conversation")
        db.add(session)
        db.commit()
        db.refresh(session)

    session_id = session.id

    past_messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    formatted_history = [
        {"role": m.role, "content": m.content}
        for m in past_messages[-10:]
    ]

    initial_state = {
        "messages": formatted_history + [{"role": "user", "content": request.question}],
        "summary": "",
        "question": request.question,
        "rewritten_query": "",
        "documents": [],
        "route": "vectorstore",
        "generation": "",
        "citations": [],
        "relevance_score": 1.0,
        "session_id": session_id,
        "user_id": user_id,
        "document_ids": request.document_ids
    }

    logger.info(f"[ChatAPI] Invoking LangGraph RAG Agent for Session: {session_id}")
    
    try:
        final_state = rag_agent_app.invoke(initial_state)
    except Exception as e:
        logger.error(f"[ChatAPI] LangGraph RAG execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG Agent execution failed: {str(e)}"
        )

    answer = final_state.get("generation", "No response generated.")
    raw_citations = final_state.get("citations", [])
    route_taken = final_state.get("route", "vectorstore")
    relevance_score = final_state.get("relevance_score", 1.0)

    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=request.question
    )
    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=answer,
        citations=raw_citations,
        route_taken=route_taken
    )
    db.add_all([user_msg, assistant_msg])

    current_title = session.title
    if is_new_session or session.title == "New Conversation" or len(past_messages) == 0:
        new_title = generate_chat_title(request.question, answer)
        session.title = new_title
        current_title = new_title

    session.updated_at = datetime.now(ZoneInfo("Asia/Kolkata"))
    db.commit()

    formatted_citations = [
        CitationSchema(
            document_id=c.get("document_id"),
            filename=c.get("filename"),
            page_number=c.get("page_number"),
            sheet_name=c.get("sheet_name"),
            chunk_index=c.get("chunk_index", 0),
            text_preview=c.get("text_preview", "")
        )
        for c in raw_citations
    ]

    return ChatResponse(
        answer=answer,
        session_id=session_id,
        title=current_title,
        citations=formatted_citations,
        route_taken=route_taken,
        relevance_score=relevance_score
    )


@router.get("/sessions", response_model=List[ChatSessionSummary], summary="List user chat sessions")
async def list_chat_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists all conversation sessions for the authenticated user, ordered by most recent."""
    sessions = (
        db.query(
            ChatSession.id,
            ChatSession.title,
            ChatSession.created_at,
            ChatSession.updated_at,
            func.count(ChatMessage.id).label("message_count")
        )
        .outerjoin(ChatMessage, ChatSession.id == ChatMessage.session_id)
        .filter(ChatSession.user_id == current_user.id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    return [
        ChatSessionSummary(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=s.message_count
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail, summary="Get session message history")
async def get_chat_session_detail(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves full conversation history and citations for a specific session."""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    formatted_messages = []
    for m in messages:
        citations = []
        if m.citations:
            for c in m.citations:
                citations.append(CitationSchema(**c))

        formatted_messages.append(
            ChatMessageItem(
                id=m.id,
                role=m.role,
                content=m.content,
                citations=citations if citations else None,
                route_taken=m.route_taken,
                created_at=m.created_at
            )
        )

    return ChatSessionDetail(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        messages=formatted_messages
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete chat session")
async def delete_chat_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes a chat session and all associated message history."""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    db.delete(session)
    db.commit()
    return None
