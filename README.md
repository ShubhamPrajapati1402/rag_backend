# Noesis - Enterprise RAG Platform Backend

A high-performance, production-grade backend for **Noesis** — an Agentic Retrieval-Augmented Generation (RAG) platform. Built with **FastAPI**, **LangGraph**, **PostgreSQL (Supabase pgvector)**, **Redis**, and a multi-format document ingestion engine.

---

## Architecture Overview

```mermaid
flowchart TB
    subgraph ClientLayer ["Client Layer"]
        Frontend["Frontend (Port :1001)"]
    end

    subgraph APILayer ["FastAPI Gateway (Port :2001)"]
        CORSMiddleware["CORS (Credentials Allowed)"]
        AuthRouter["/api/v1/auth (Authentication)"]
        ChatRouter["/api/v1/chat (Stateful LangGraph RAG)"]
        IngestRouter["/api/v1/ingest (Ingestion Engine)"]
        HealthRouter["/health (Healthcheck)"]
    end

    subgraph SecurityServices ["Security & Auth Services"]
        JWTService["JWT Handler (PyJWT)"]
        BcryptHandler["Password Hashing (bcrypt)"]
        GoogleOAuth["Google ID Token Verifier"]
        OTPManager["Redis OTP Engine (Rate Limited)"]
        EmailService["Async SMTP / Dev Logger"]
    end

    subgraph AgenticRAG ["Stateful LangGraph RAG Core"]
        Summarizer["Node 1: Progressive Summarizer"]
        Router["Node 2: Semantic Router"]
        Rewriter["Node 3: Contextual Query Rewriter"]
        Retriever["Node 4: pgvector Cosine Retriever"]
        Grader["Node 5: Parallel Doc Grader (asyncio.gather)"]
        Generator["Node 6: Grounded Generator & Citations"]
    end

    subgraph IngestionPipeline ["Data Ingestion & Vector Engine"]
        ParserRegistry["Multi-Format Parser Registry (10+ Formats)"]
        Classifier["PDF Hybrid Classifier (fast / hi_res)"]
        Chunker["Semantic Chunking Engine"]
        Embedder["Hugging Face Inference (BAAI/bge-m3)"]
        LiveIngestStream["Dynamic Layman SSE Stream"]
    end

    subgraph DataLayer ["Storage & Caching Layer"]
        PostgreSQL[("PostgreSQL / Supabase (pgvector)")]
        RedisStore[("Redis Cache (OTP, TTL, Rate Limits)")]
    end

    Frontend --> CORSMiddleware
    CORSMiddleware --> AuthRouter
    CORSMiddleware --> ChatRouter
    CORSMiddleware --> IngestRouter
    CORSMiddleware --> HealthRouter

    AuthRouter --> SecurityServices
    SecurityServices --> RedisStore
    SecurityServices --> PostgreSQL

    ChatRouter --> AgenticRAG
    AgenticRAG --> PostgreSQL

    IngestRouter --> IngestionPipeline
    IngestionPipeline --> PostgreSQL
```

---

## Core Systems & Features

### 1. Production Authentication & Security Subsystem
* **Zero Hardcoded Secrets**: All ports, origins, secrets, cookie flags, and token expiries are strictly loaded from `.env` via Pydantic `Settings`.
* **HttpOnly Secure Session Cookies**: Prevents Cross-Site Scripting (XSS) token theft. The browser automatically manages and includes authentication cookies with `SameSite=Lax` protection.
* **Redis-Backed OTP Engine**:
  * **Zero Database Overhead**: Ephemeral 6-digit verification codes are stored in Redis with automatic TTL expiration (`OTP_EXPIRE_SECONDS`).
  * **Spam Cooldown Guard**: Enforces a configurable cooldown period (`OTP_RESEND_COOLDOWN_SECONDS`) between successive resend requests.
  * **Hourly Request Ceiling**: Limits maximum OTP requests per email (`OTP_MAX_REQUESTS_PER_HOUR`) to prevent abuse and API exhaustion.
  * **Anti-Brute Force Lockout**: Tracks failed verification attempts. After `OTP_MAX_VERIFY_ATTEMPTS` incorrect attempts, the OTP is destroyed and the email is locked out for `OTP_LOCKOUT_SECONDS` with an HTTP `429 Too Many Requests`.
* **Google OAuth2 Authentication**: Decoupled verification of Google ID tokens using official Google public certificates, with automated account provisioning and profile synchronization.
* **User-Scoped Data Storage**: SQLAlchemy `User` model with relational binding to `Document`, `ChatSession`, and `ChatMessage` records (`user_id` foreign key).

---

### 2. Multi-Format Data Ingestion Engine & Dynamic Live Progress Stream
* **10+ Supported Formats**: Native parsing for PDF, Markdown, DOCX, CSV, TSV, Excel (`.xlsx`, `.xls`), HTML, JSON, PPTX, XML, and TXT via `ParserRegistry`.
* **Dynamic Layman SSE Stream (`POST /api/v1/ingest/stream`)**: Calculates and streams dynamic, genuine progress based on page counts and embedding batches in friendly layman terms (e.g. *"Teaching AI concepts (16 of 42 sections learned)..."*).
* **Hybrid PDF Parsing**: Scans pages with `pdfplumber` to route complex tables to `hi_res` OCR and simple pages to `fast` extraction.
* **Semantic & Format-Specific Chunking**: Strict sheet boundary isolation for Excel, heading breadcrumb hierarchies (`# H1 > ## H2`) for Markdown/DOCX, and slide-level isolation for PPTX.
* **Idempotency & Resumability**: SHA-256 file hashing, config hash drift protection, and atomic document leases.

---

### 3. Stateful LangGraph RAG Agent & Live Thought Tracing
* **6-Node Reasoning Graph**:
  1. **Summarizer Node**: Progressively condenses multi-turn conversations into a running cumulative summary when history $\ge 4$ messages so zero long-range context is truncated.
  2. **Router Node**: Classifies queries into direct conversational answers vs. vector database retrieval.
  3. **Query Rewriter Node**: Resolves conversational pronouns and context across prior turns into standalone search queries.
  4. **Vector Retriever Node**: Cosine distance similarity search over PostgreSQL `document_chunks` using `BAAI/bge-m3` 1024-dimensional embeddings.
  5. **Document Grader Node**: Evaluates candidate chunks concurrently with Groq LLM (`asyncio.gather`) to filter out noise before generation in ~200ms.
  6. **Grounded Generator & Guard**: Synthesizes answers strictly from verified context and formats source citations.
* **Server-Sent Events (SSE) Streaming (`POST /api/v1/chat/stream`)**:
  * **Live Thought Tracing (`event: trace`)**: Streams active reasoning thoughts (e.g. *"Analyzing question intent..."*, *"Searching vector database for high-similarity document excerpts..."*, *"Verified 3 relevant excerpts (Confidence: 85%)"*).
  * **Real-time LLM Tokens (`event: token`)**: Sub-second token delivery directly to the client from generator nodes.
  * **Structured Source Citations (`event: citations`)**: Returns verified file names, page numbers, and text previews.
* **Intelligent Semantic Titling**: Generates concise 3-to-6 word titles for conversations using the LLM without hard character slicing.
* **Persistent PostgreSQL Conversation Store**: `chat_sessions` and `chat_messages` tables store full message histories, citations, and routing paths scoped to `user_id`.

---

## Tech Stack

| Component | Technology |
| :--- | :--- |
| **Language & Runtime** | Python 3.10+ / `uv` |
| **Web Framework** | FastAPI |
| **Agentic Framework** | LangGraph / LangChain Core |
| **Database ORM** | SQLAlchemy 2.0 (with `pgvector`) |
| **Database & Vector Store** | PostgreSQL (Supabase Cloud) |
| **Cache & OTP Engine** | Redis 5.0+ |
| **Security & Auth** | PyJWT, bcrypt, Google Auth, HttpOnly Cookies |
| **Embeddings Model** | Hugging Face Inference API (`BAAI/bge-m3` 1024-dim) |
| **LLM Inference** | Groq API (`llama-3.3-70b-versatile` / `gpt-oss-20b`, `temp=0.2`) |
| **Document Parsers** | `unstructured`, `pdfplumber`, `markdown-it-py`, `pandas`, `python-docx`, `python-pptx`, `beautifulsoup4` |
| **Testing** | `pytest`, `httpx`, `fakeredis`, `anyio` |

---

## Project Structure

```text
rag_backend/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── auth.py             # Auth endpoints (signup, verify-otp, login, google, me, logout)
│   │   │   ├── chat.py             # Stateful LangGraph RAG & SSE streaming endpoints
│   │   │   └── ingest.py           # Dynamic SSE document upload, list & delete endpoints
│   │   ├── deps.py                 # FastAPI dependencies (get_current_user from HttpOnly cookies)
│   │   └── router.py               # API root router (/api/v1)
│   ├── core/
│   │   ├── config.py               # Pydantic Settings (.env validator)
│   │   ├── redis_client.py         # Redis connection pool & healthcheck
│   │   └── security.py             # bcrypt hashing, JWT encode/decode, cookie managers
│   ├── db/
│   │   └── session.py              # SQLAlchemy database engine, session maker & auto-migrations
│   ├── models/
│   │   ├── chat.py                 # ChatSession and ChatMessage models
│   │   ├── document.py             # Document & DocumentChunk models (with pgvector)
│   │   ├── document_element.py     # Structured parser document elements
│   │   └── user.py                 # User model (auth_provider, verification, timestamps)
│   ├── schemas/
│   │   ├── chat_schemas.py         # Pydantic request/response schemas for RAG chat
│   │   ├── rag_state.py            # TypedDict state schema for LangGraph workflow
│   │   └── user.py                 # Pydantic request/response validation schemas
│   ├── scripts/
│   │   └── ingest.py               # CLI ingestion & validation runner
│   ├── services/
│   │   ├── parsers/                # Extensible format-specific parsers (PDF, CSV, MD, Excel, etc.)
│   │   ├── rag/                    # Stateful LangGraph RAG Agent System
│   │   │   ├── nodes/              # Specialized async graph nodes (router, rewriter, grader, etc.)
│   │   │   ├── graph.py            # Compiled LangGraph state graph workflow
│   │   │   ├── llm.py              # Groq LLM factory & async title generator
│   │   │   └── prompts.py          # System prompts for reasoning, grading, and summarization
│   │   ├── auth_service.py         # Authentication & registration workflows
│   │   ├── classifier.py           # PDF page complexity classifier
│   │   ├── email_service.py        # Asynchronous SMTP / development console logger
│   │   ├── embeddings.py           # Hugging Face BAAI/bge-m3 embeddings factory
│   │   ├── google_auth_service.py    # Google ID token signature verifier
│   │   ├── ingestion_service.py    # Dynamic layman SSE upload & embedding pipeline
│   │   ├── otp_service.py          # Redis-backed OTP rate limiter & validator
│   │   └── validator.py            # Chunk coverage & integrity analyzer
│   └── main.py                     # FastAPI application entrypoint & lifespan
├── data/
│   └── uploads/                    # Storage for source documents
├── tests/
│   └── test_auth.py                # Unit and integration test suite
├── .env.example                    # Environment variables template
├── pytest.ini                      # Pytest configuration
├── requirements.txt                # Project dependencies
└── README.md                       # Project documentation
```

---

## API Reference

### Base URL: `http://localhost:2001/api/v1`

#### 1. Authentication Endpoints (`/auth`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/signup` | Register new account and dispatch 6-digit OTP | No |
| `POST` | `/auth/verify-otp` | Validate OTP code, activate user, and set `HttpOnly` cookie | No |
| `POST` | `/auth/resend-otp` | Request a fresh OTP (enforces cooldown & hourly limits) | No |
| `POST` | `/auth/login` | Login with email & password and set `HttpOnly` cookie | No |
| `POST` | `/auth/google` | Sign in / sign up using Google OAuth2 ID token | No |
| `GET` | `/auth/me` | Fetch currently authenticated user profile | **Yes (Cookie)** |
| `POST` | `/auth/logout` | Clear authentication session cookie | No |

#### 2. Agentic RAG Chat Endpoints (`/chat`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/chat/stream` | Stream RAG responses with live thought tracing & tokens via SSE | **Yes (Cookie)** |
| `POST` | `/chat` | Synchronous JSON fallback endpoint for RAG queries | **Yes (Cookie)** |
| `GET` | `/chat/sessions` | List all conversation sessions with message counts | **Yes (Cookie)** |
| `GET` | `/chat/sessions/{session_id}` | Get full conversation history and structured citations | **Yes (Cookie)** |
| `DELETE` | `/chat/sessions/{session_id}` | Delete a chat session and all historical messages | **Yes (Cookie)** |

#### 3. Ingestion & Document Processing (`/ingest`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/ingest/stream` | Upload document and stream live dynamic progress via SSE | **Yes (Cookie)** |
| `GET` | `/ingest/documents` | List all user-uploaded documents and chunk counts | **Yes (Cookie)** |
| `DELETE` | `/ingest/documents/{document_id}` | Delete a document and its pgvector embeddings | **Yes (Cookie)** |

#### 4. Health Check
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Server health check and status | No |

---

## Server-Sent Events (SSE) Protocol

### Chat Streaming (`POST /api/v1/chat/stream`)
The chat stream emits the following structured events:
* `event: metadata` $\rightarrow$ `{"session_id": "...", "title": "...", "is_new_session": true}`
* `event: trace` $\rightarrow$ `{"step": "retriever", "status": "active" | "done", "thought": "Searching vector database..."}`
* `event: node_status` $\rightarrow$ `{"node": "router", "status": "started" | "completed", "route": "vectorstore"}`
* `event: token` $\rightarrow$ `{"text": "The Q3 operating margin was..."}`
* `event: citations` $\rightarrow$ `{"citations": [{"filename": "Financials.xlsx", "page_number": 1, ...}]}`
* `event: done` $\rightarrow$ `{"session_id": "...", "title": "...", "route_taken": "vectorstore"}`

### Ingestion Progress Streaming (`POST /api/v1/ingest/stream`)
The ingestion stream emits live progress calculated from page count and batch embeddings:
* `event: progress` $\rightarrow$ `{"percent": 68, "stage": "embedding", "message": "Teaching AI concepts (16 of 42 sections learned)..."}`
* `event: done` $\rightarrow$ `{"percent": 100, "status": "completed", "message": "Ready to chat!"}`
* `event: error` $\rightarrow$ `{"error": "...", "message": "..."}`

---

## Getting Started

### 1. Prerequisites
- [Python 3.10+](https://www.python.org/)
- [`uv`](https://github.com/astral-sh/uv) (recommended package and project manager)
- [Redis](https://redis.io/) running locally or via cloud (e.g. Upstash)

### 2. Environment Setup
1. Clone the repository and navigate into `rag_backend`:
   ```powershell
   cd "d:\Learning AI\RAG\rag_backend"
   ```

2. Copy the `.env.example` file to create your `.env`:
   ```powershell
   cp .env.example .env
   ```

3. Configure your variables inside `.env`:
   ```env
   # Database (Supabase PostgreSQL)
   DATABASE_URL="postgresql://postgres.[REF]:[PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"

   # Server & CORS
   BACKEND_HOST="0.0.0.0"
   BACKEND_PORT=2001
   FRONTEND_URL="http://localhost:1001"
   CORS_ORIGINS=["http://localhost:1001","http://127.0.0.1:1001"]

   # JWT & Cookies
   SECRET_KEY="your-super-secret-jwt-key"
   ALGORITHM="HS256"
   ACCESS_TOKEN_EXPIRE_MINUTES=10080
   COOKIE_NAME="auth_token"
   COOKIE_SECURE=False
   COOKIE_SAMESITE="lax"

   # Redis & OTP
   REDIS_URL="redis://localhost:6379/0"
   OTP_LENGTH=6
   OTP_EXPIRE_SECONDS=600
   OTP_RESEND_COOLDOWN_SECONDS=60
   OTP_MAX_REQUESTS_PER_HOUR=5
   OTP_MAX_VERIFY_ATTEMPTS=5
   OTP_LOCKOUT_SECONDS=900

   # Google OAuth
   GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
   GOOGLE_CLIENT_SECRET="your-client-secret"

   # Groq & Hugging Face
   GROQ_API_KEY="gsk_..."
   GROQ_MODEL_NAME="llama-3.3-70b-versatile"
   HUGGINGFACE_API_KEY="hf_..."
   HUGGINGFACE_EMBEDDING_MODEL="BAAI/bge-m3"
   ```

4. Install dependencies using `uv`:
   ```powershell
   uv pip install -r requirements.txt
   ```

---

## Running the Application

### 1. Start the FastAPI Web Server
```powershell
uv run python app/main.py
```
* **API Documentation (Swagger UI)**: [http://localhost:2001/docs](http://localhost:2001/docs)
* **Interactive ReDoc**: [http://localhost:2001/redoc](http://localhost:2001/redoc)

### 2. Running Automated Tests
Run the test suite with `pytest`:
```powershell
uv run pytest -v
```

### 3. Running the Ingestion Engine CLI
To ingest documents directly into Supabase vector store via terminal:
```powershell
uv run python app/scripts/ingest.py "data/uploads/your_document.pdf"
```

#### Benchmark / Dry-Run Mode:
Extract and validate chunking without writing to the database:
```powershell
uv run python app/scripts/ingest.py --validate "data/uploads/your_document.pdf"
```
