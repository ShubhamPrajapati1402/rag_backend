import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_current_user
from app.db.session import get_db, SessionLocal
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.services.rag.llm import generate_chat_title, agenerate_chat_title
from app.services.rag.nodes.summarizer import summarizer_node
from app.services.rag.nodes.router import router_node
from app.services.rag.nodes.rewriter import rewriter_node
from app.services.rag.nodes.grader import grader_node
from app.services.rag.nodes.generator import rag_generator_node, direct_generator_node

# Seeded or mocked user
@pytest.fixture
def db_session():
    db = SessionLocal()
    user = db.query(User).filter(User.email == "testraguser@example.com").first()
    if not user:
        user = User(
            email="testraguser@example.com",
            hashed_password="mockpasswordhash",
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    yield db, user
    db.query(ChatSession).filter(ChatSession.user_id == user.id).delete()
    db.commit()
    db.close()

@pytest.fixture
def client(db_session):
    db, user = db_session
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_llm_title_generation_no_truncation():
    """Verify that title generation produces clean semantic titles without hard string slicing."""
    with patch("app.services.rag.llm.get_groq_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = 'Title: "World Bank FY2025 Financial Summary"'
        mock_get_llm.return_value = mock_llm

        title = generate_chat_title(
            question="What is the net revenue of the World Bank for 2025?",
            response="The total commitments reached $70 billion in FY2025."
        )

        assert title == "World Bank FY2025 Financial Summary"
        assert not title.startswith("Title:")
        assert '"' not in title
        assert len(title) > 25


@pytest.mark.anyio
async def test_summarizer_node_compresses_history():
    """Verify summarizer generates a running summary when conversation length >= 4."""
    with patch("app.services.rag.nodes.summarizer.get_groq_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="User inquired about World Bank commitments in FY2025 which reached $70 billion."))
        mock_get_llm.return_value = mock_llm

        state = {
            "summary": "",
            "messages": [
                {"role": "user", "content": "Tell me about World Bank"},
                {"role": "assistant", "content": "The World Bank is a multilateral development institution."},
                {"role": "user", "content": "What were their FY2025 commitments?"},
                {"role": "assistant", "content": "Total commitments were $70 billion."}
            ]
        }
        result = await summarizer_node(state)
        assert "World Bank" in result["summary"]
        assert "$70 billion" in result["summary"]


@pytest.mark.anyio
async def test_router_node_direct_greeting():
    """Verify router classifies greetings as direct response."""
    state = {"question": "Hello", "messages": [], "summary": ""}
    result = await router_node(state)
    assert result["route"] == "direct"


@pytest.mark.anyio
async def test_router_node_document_query():
    """Verify router classifies document questions as vectorstore."""
    with patch("app.services.rag.nodes.router.get_groq_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='{"route": "vectorstore", "reason": "Asks about report tables"}'))
        mock_get_llm.return_value = mock_llm

        state = {"question": "What is the net loan loss provision on page 42?", "messages": [], "summary": ""}
        result = await router_node(state)
        assert result["route"] == "vectorstore"


@pytest.mark.anyio
async def test_rewriter_node_preserves_single_turn():
    """Verify rewriter keeps standalone single-turn questions."""
    state = {"question": "What are the total assets of IDA?", "messages": [], "summary": ""}
    result = await rewriter_node(state)
    assert result["rewritten_query"] == "What are the total assets of IDA?"


@pytest.mark.anyio
async def test_rewriter_node_resolves_pronouns():
    """Verify rewriter expands pronouns in multi-turn conversation with summary."""
    with patch("app.services.rag.nodes.rewriter.get_groq_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='{"rewritten_query": "What is the capital adequacy ratio of IBRD?"}'))
        mock_get_llm.return_value = mock_llm

        state = {
            "question": "What is its capital adequacy ratio?",
            "summary": "Discussion regarding IBRD's balance sheet and solvency.",
            "messages": [
                {"role": "user", "content": "Tell me about IBRD"},
                {"role": "assistant", "content": "IBRD is the International Bank for Reconstruction and Development."}
            ]
        }
        result = await rewriter_node(state)
        assert "IBRD" in result["rewritten_query"]


@pytest.mark.anyio
async def test_grader_node_filters_irrelevant_chunks():
    """Verify document grader retains relevant chunks in parallel and calculates score."""
    with patch("app.services.rag.nodes.grader.get_groq_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=[
            MagicMock(content='{"is_relevant": true}'),
            MagicMock(content='{"is_relevant": false}')
        ])
        mock_get_llm.return_value = mock_llm

        state = {
            "question": "Revenue in 2025",
            "rewritten_query": "Revenue in 2025",
            "documents": [
                {"filename": "report.pdf", "text_content": "Total revenue in FY2025 was $50B.", "page_number": 10},
                {"filename": "menu.docx", "text_content": "Cafeteria lunch menu for Tuesday.", "page_number": 1}
            ]
        }
        result = await grader_node(state)
        assert len(result["documents"]) == 1
        assert result["documents"][0]["filename"] == "report.pdf"
        assert result["relevance_score"] == 0.5


@pytest.mark.anyio
async def test_generator_node_creates_structured_citations():
    """Verify generator formats citations and grounds answer."""
    with patch("app.services.rag.nodes.generator.get_groq_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="The net income for FY2025 was $4.5 billion."))
        mock_get_llm.return_value = mock_llm

        state = {
            "question": "What is the net income?",
            "documents": [
                {
                    "document_id": 1,
                    "filename": "annual_report.pdf",
                    "page_number": 45,
                    "sheet_name": None,
                    "chunk_index": 3,
                    "text_content": "Net income reached $4.5B in FY2025."
                }
            ]
        }
        result = await rag_generator_node(state)
        assert "net income" in result["generation"].lower()
        assert len(result["citations"]) == 1
        assert result["citations"][0]["filename"] == "annual_report.pdf"
        assert result["citations"][0]["page_number"] == 45


def test_chat_api_endpoint(client):
    """Verify POST /api/v1/chat endpoint returns structured ChatResponse and creates session."""
    with patch("app.api.routes.chat.rag_agent_app.invoke") as mock_invoke, \
         patch("app.api.routes.chat.generate_chat_title") as mock_title:
        
        mock_invoke.return_value = {
            "generation": "Hello! I am Noesis, your enterprise AI assistant.",
            "citations": [],
            "route": "direct",
            "relevance_score": 1.0,
            "summary": ""
        }
        mock_title.return_value = "Enterprise Assistant Greeting"

        response = client.post(
            "/api/v1/chat",
            json={"question": "Hello!"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Hello! I am Noesis, your enterprise AI assistant."
        assert data["title"] == "Enterprise Assistant Greeting"
        assert data["route_taken"] == "direct"
        assert "session_id" in data


def test_sse_chat_stream_endpoint(client):
    """Verify POST /api/v1/chat/stream streams SSE events (metadata, tokens, done)."""
    async def mock_astream_events(*args, **kwargs):
        yield {"event": "on_chain_start", "name": "router"}
        yield {"event": "on_chain_end", "name": "router", "data": {"output": {"route": "direct"}}}
        
        mock_chunk = MagicMock()
        mock_chunk.content = "Streaming response token"
        yield {"event": "on_chat_model_stream", "data": {"chunk": mock_chunk}}

    with patch("app.api.routes.chat.rag_agent_app.astream_events", side_effect=mock_astream_events), \
         patch("app.api.routes.chat.agenerate_chat_title", AsyncMock(return_value="Streaming Chat Title")):
        
        response = client.post(
            "/api/v1/chat/stream",
            json={"question": "Stream this test"}
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "event: metadata" in body
        assert "event: node_status" in body
        assert "event: token" in body
        assert "event: done" in body
