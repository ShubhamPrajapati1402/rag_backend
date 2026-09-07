# Noesis - Enterprise Agentic RAG Platform Backend

A high-performance, production-grade backend for **Noesis** — an Agentic Retrieval-Augmented Generation (RAG) platform. Built with **FastAPI**, **LangGraph**, **PostgreSQL (Supabase pgvector)**, **Redis**, a 100% free multimodal voice layer (Groq Whisper STT + Microsoft Neural Voice Edge-TTS), intelligent dual-mode document scoping, and a continuous RAGAs evaluation engine.

---

## Architecture Overview

```mermaid
flowchart TB
    subgraph ClientLayer ["Client Layer (React 19 + TypeScript)"]
        Frontend["Frontend Studio (Port :1001)"]
        WebSocketClient["WebSocket Presence (/ws/developer-team)"]
        VoiceStudio["Voice Typing & Instant Audio (<15ms)"]
    end

    subgraph APILayer ["FastAPI Gateway (Port :2001)"]
        CORSMiddleware["CORS (Credentials Allowed)"]
        AuthRouter["/api/v1/auth (Auth & 3-Tier RBAC)"]
        ChatRouter["/api/v1/chat (Stateful LangGraph RAG)"]
        VoiceRouter["/api/v1/voice (STT & Neural TTS)"]
        IngestRouter["/api/v1/ingest (Multi-Format Ingestion)"]
        EvalRouter["/api/v1/eval (RAGAs Benchmark Suite)"]
        WSRouter["/ws/developer-team (Real-Time Pub/Sub Hub)"]
        HealthRouter["/health (Healthcheck)"]
    end

    subgraph SecurityServices ["Security & RBAC Services"]
        JWTService["JWT Handler (PyJWT)"]
        BcryptHandler["Password Hashing (bcrypt)"]
        GoogleOAuth["Google ID Token Verifier"]
        OTPManager["Redis OTP Engine (Rate Limited)"]
        EmailService["Async SMTP (OTP & Tokenized Invites)"]
        WSManager["Redis Pub/Sub Connection Manager"]
    end

    subgraph VoiceEngine ["Multimodal Voice Layer (100% Free)"]
        WhisperSTT["Groq Whisper Large v3 Turbo (STT)"]
        SilenceFilter["Whisper Silence Hallucination Filter"]
        EdgeTTS["Microsoft Edge-TTS Neural Audio Streamer"]
        TTSCache["In-Memory LRU Audio Cache (<1ms Replay)"]
        TextSanitizer["Markdown & Citation Sanitizer"]
    end

    subgraph LLMChain ["Multi-Tier Resilient LLM Fallback Chain"]
        Tier1["Tier 1: Google Gemini (gemini-flash-latest)"]
        Tier2["Tier 2: Groq LPU (openai/gpt-oss-120b)"]
        Tier3["Tier 3: Groq Fallback (openai/gpt-oss-20b)"]
        FastTitleGen["Groq LPU Instant Title Generator (~200ms)"]
    end

    subgraph AgenticRAG ["Stateful LangGraph RAG Core (8-Node Pipeline)"]
        Summarizer["Node 1: Progressive Summarizer"]
        InputGuard["Node 2: Security & Prompt Injection Guardrail"]
        Router["Node 3: Semantic Router"]
        Rewriter["Node 4: Dual-Mode Contextual Query Rewriter (0ms Fast Pass)"]
        Retriever["Node 5: Stage 1 High-Recall pgvector Retriever (top_k=20)"]
        Reranker["Node 6: Stage 2 Single-Doc Fast / Groq Listwise Reranker"]
        Grader["Node 7: Parallel Document Grader (asyncio.gather)"]
        Generator["Node 8: Grounded Generator & Citations"]
        HallucinationGuard["Node 9: Groundedness Audit Guardrail"]
    end

    subgraph IngestionPipeline ["Data Ingestion & Vector Engine"]
        ParserRegistry["Multi-Format Parser Registry (10+ Formats)"]
        Classifier["PDF Hybrid Classifier (fast / hi_res)"]
        Chunker["Semantic Chunking Engine"]
        Embedder["Hugging Face Inference (BAAI/bge-m3)"]
        LiveIngestStream["Dynamic Layman SSE Stream"]
    end

    subgraph EvaluationSuite ["Continuous RAGAs Benchmark Suite"]
        QAGenerator["Multi-Doc Synthetic QA Generator"]
        FaithfulnessJudge["Context Entailment Judge (0-1)"]
        RelevanceJudge["Query Intent Relevance Judge (0-1)"]
        PrecisionJudge["Rank #1 Mean Precision Judge (0-1)"]
        RecallJudge["Fact Coverage Recall Judge (0-1)"]
        ClaimsAudit["Atomic Sentence Claim Audit"]
    end

    subgraph DataLayer ["Storage, Migrations & Caching Layer"]
        PostgreSQL[("PostgreSQL / Supabase (pgvector)")]
        DBMigrations["Version-Tracked Idempotent SQL Migrations"]
        RedisStore[("Redis Cache (OTP, TTL, Pub/Sub Cluster)")]
    end

    Frontend --> CORSMiddleware
    WebSocketClient --> WSRouter
    VoiceStudio --> VoiceRouter
    CORSMiddleware --> AuthRouter
    CORSMiddleware --> ChatRouter
    CORSMiddleware --> VoiceRouter
    CORSMiddleware --> IngestRouter
    CORSMiddleware --> EvalRouter
    CORSMiddleware --> HealthRouter

    AuthRouter --> SecurityServices
    SecurityServices --> RedisStore
    SecurityServices --> PostgreSQL
    WSRouter --> WSManager
    WSManager --> RedisStore

    VoiceRouter --> VoiceEngine
    VoiceEngine --> WhisperSTT
    VoiceEngine --> EdgeTTS

    ChatRouter --> AgenticRAG
    AgenticRAG --> LLMChain
    AgenticRAG --> PostgreSQL

    IngestRouter --> IngestionPipeline
    IngestionPipeline --> PostgreSQL

    EvalRouter --> EvaluationSuite
    EvaluationSuite --> LLMChain
    EvaluationSuite --> PostgreSQL
```

---

## Core Systems & Features

### 1. 100% Free Studio Multimodal Voice Layer (STT & TTS)
* **High-Speed Speech-to-Text (STT)**:
  * Powered by **Groq Whisper Large v3 Turbo** (`POST /api/v1/voice/stt`) for lightning-fast voice transcription (~300ms).
  * Inbuilt **Silence Hallucination Filter** automatically detects and suppresses common Whisper phantom phrases (*"Thank you for watching"*, *"Please subscribe"*).
* **Neural Text-to-Speech (TTS) Streaming**:
  * Real-time MP3 streaming via **Microsoft Neural Edge-TTS** (`GET /api/v1/voice/tts`, `POST /api/v1/voice/tts`).
  * **In-Memory LRU Audio Cache**: Repeated phrases and previously synthesized message audio return in **< 1ms** from server RAM.
  * **HTTP Caching & Range Headers**: Returns `ETag`, `Cache-Control: public, max-age=86400`, and `Accept-Ranges: bytes` for zero-lag browser-cached replays.
  * **Intelligent Markdown Sanitizer**: Strips code blocks, footnotes, raw URLs, headers, and bullet dashes before synthesis for natural, uninterrupted speech.
* **Curated Voice Profiles (`GET /api/v1/voice/voices`)**:
  * `en-US-ChristopherNeural` (Male, Professional & Authoritative)
  * `en-US-JennyNeural` (Female, Natural & Friendly)
  * `en-IN-PrabhatNeural` (Male, Indian English Clear & Professional)
  * `en-IN-NeerjaNeural` (Female, Indian English Warm & Articulate)
  * `en-GB-RyanNeural` (Male, British English Refined & Polished)
  * `en-GB-SoniaNeural` (Female, British English Engaging & Expressive)

---

### 2. Intelligent Dual-Mode Document Scoping & Routing Engine
* **Mode 1: Explicit `@Mention` File Tagging**:
  * When documents are tagged by the user in the prompt bar, the rewriter activates a **0ms Fast Pass-Through** and vector retrieval strictly filters against the specified `selected_documents`.
* **Mode 2: ChatGPT-Style Automatic Intent Scoping**:
  * When no explicit tags are provided, the query rewriter analyzes the prompt against the user's active document list. If the user refers to a document implicitly (*"What is the revenue in the 2025 annual report?"*), it automatically resolves and attaches the target document scope.

---

### 3. Multi-Tier Resilient LLM Fallback Chain
* **Dynamic Configuration (`.env`)**:
  * Primary: `GEMINI_MODEL_NAME="gemini-flash-latest"`
  * Fallback Tier 1: `GROQ_MODEL_NAME="openai/gpt-oss-120b"`
  * Fallback Tier 2: `GROQ_FALLBACK_MODEL_NAME="openai/gpt-oss-20b"`
* **Automatic Quota & Failover Protection**:
  * Seamlessly catches Google 429 Quota Exceeded and 503 Service Unavailable errors and falls back to Groq LPUs without dropping the user's stream.
  * Automatic legacy model remapping ensures historical sessions remain fully operational.
* **Instant Groq LPU Title Generation**:
  * Generates session chat titles in **~200ms** (`agenerate_chat_title`) without adding delay to the conversation turn.

---

### 4. Stateful LangGraph RAG Core (8-Node Pipeline)
* **Progressive History Summarization**: Incrementally condenses conversation turns to preserve long-term context within token limits.
* **Security & Prompt Injection Guardrail**: Sanitizes inputs and halts adversarial prompt injection attempts.
* **Semantic Intent Router**: Directs conversational queries, factual lookups, and clarification workflows.
* **Dual-Mode Contextual Query Rewriter**: Contextualizes user queries with 0ms fast-path for tagged documents.
* **Stage 1 High-Recall pgvector Retrieval**: Hybrid vector similarity (`BAAI/bge-m3`) with top-k recall.
* **Stage 2 Adaptive Reranker**: Employs $0\text{ms}$ fast RRF ordering for single-document scopes ($\le 5$ chunks) and Groq LPU listwise reranking for multi-document candidates.
* **Parallel Document Relevance Grader**: Verifies candidate chunk relevance concurrently via `asyncio.gather`.
* **Grounded Answer Generator & Citations**: Synthesizes verified answers with page, row, and section-level source citations.

---

### 5. Idempotent Version-Tracked Database Migrations
* **Automatic Startup Migrations**: `app/db/migrations/` tracks applied SQL migrations in a dedicated `schema_migrations` ledger table.
* **Zero-Downtime Schema Evolution**: Automatically applies new column additions, foreign keys, and indexes on server boot without manual SQL execution.

---

### 6. 3-Tier Role-Based Access Control (RBAC) & Developer Collaboration
* **Super Admin (`👑`)**: Root platform owner defined in `DEVELOPER_EMAILS`. Can manage team roles and run benchmarks.
* **Admin (`🛡️`)**: Team administrator. Can invite members with tokenized 48-hour links (`/api/v1/auth/invite-developer`).
* **Member (`💻`)**: Analyst / Developer. Can execute RAGAs benchmarks and audit atomic claim scorecards.
* **Real-Time WebSocket Sync (`/ws/developer-team`)**: Synchronizes team presence and role changes in real time across active clients.

---

## API Endpoints Reference

### Voice Layer (`/api/v1/voice`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/voice/stt` | Transcribe speech audio to text using Groq Whisper Large v3 Turbo | Public / Optional Auth |
| `GET` | `/api/v1/voice/tts` | Stream neural MP3 audio directly to HTML5 `<audio>` elements | Public / Optional Auth |
| `POST` | `/api/v1/voice/tts` | Synthesize neural MP3 audio with voice, rate, and pitch parameters | Public / Optional Auth |
| `GET` | `/api/v1/voice/voices` | List curated Microsoft neural voices with accent & gender metadata | Public |

### Chat & Streaming (`/api/v1/chat`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/chat/message` | Synchronous invocation through LangGraph RAG pipeline | Authenticated |
| `POST` | `/api/v1/chat/stream` | Server-Sent Events (SSE) streaming token output & node status | Authenticated |
| `GET` | `/api/v1/chat/sessions` | List user conversation sessions with message counts | Authenticated |
| `GET` | `/api/v1/chat/sessions/{id}` | Hydrate message history and citations for a session | Authenticated |
| `DELETE` | `/api/v1/chat/sessions/{id}` | Delete a chat session and associated messages | Authenticated |

### Document Ingestion (`/api/v1/ingest`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/ingest/upload` | Upload and parse multi-format documents (10+ formats) | Authenticated |
| `POST` | `/api/v1/ingest/stream` | Stream dynamic Layman SSE ingestion progress | Authenticated |
| `GET` | `/api/v1/ingest/documents` | List indexed documents and chunk statistics | Authenticated |
| `DELETE` | `/api/v1/ingest/documents/{id}` | Delete document and remove embeddings from pgvector | Authenticated |

### Authentication & RBAC (`/api/v1/auth`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/signup` | Register new account and dispatch 6-digit OTP | Public |
| `POST` | `/api/v1/auth/verify-otp` | Verify OTP and issue HttpOnly session cookie | Public |
| `POST` | `/api/v1/auth/login` | Email/password login | Public |
| `POST` | `/api/v1/auth/google` | Google OAuth2 ID token authentication | Public |
| `POST` | `/api/v1/auth/logout` | Clear active session | Authenticated |
| `GET` | `/api/v1/auth/me` | Fetch active user profile and developer role | Authenticated |
| `GET` | `/api/v1/auth/developers` | List active team developers and pending invitations | Developer |
| `POST` | `/api/v1/auth/invite-developer` | Send tokenized invitation email with role | Admin / Super Admin |
| `POST` | `/api/v1/auth/accept-invite` | Accept invitation and activate developer role | Authenticated |

### Evaluation Suite (`/api/v1/eval`)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/eval/runs` | List historical benchmark runs with composite scores | Developer |
| `GET` | `/api/v1/eval/runs/{run_id}` | Granular test cases & atomic claim verification audits | Developer |
| `POST` | `/api/v1/eval/runs` | Trigger dynamic multi-document RAG benchmark | Developer |
| `DELETE` | `/api/v1/eval/runs/{run_id}` | Delete evaluation run and test cases | Developer |

---

## Local Setup & Development

### 1. Prerequisites
* **Python 3.10+** (or `uv` package manager)
* **PostgreSQL** with `pgvector` extension (or Supabase instance)
* **Redis** (Local or Redis Cloud)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/ShubhamPrajapati1402/rag_backend.git
cd rag_backend

# Install dependencies using uv
uv pip install -r requirements.txt
```

### 3. Environment Setup
```bash
cp .env.example .env
```
Configure your `.env` variables:
```env
# Database & Redis
DATABASE_URL="postgresql://user:password@localhost:5432/rag_db"
REDIS_URL="redis://localhost:6379/0"

# LLM Providers
GEMINI_API_KEY="AIzaSy..."
GEMINI_MODEL_NAME="gemini-flash-latest"
GROQ_API_KEY="gsk_..."
GROQ_MODEL_NAME="openai/gpt-oss-120b"
GROQ_FALLBACK_MODEL_NAME="openai/gpt-oss-20b"

# Voice Layer (STT & TTS)
VOICE_STT_MODEL="whisper-large-v3-turbo"
VOICE_DEFAULT_TTS_VOICE="en-US-ChristopherNeural"
```

### 4. Running the Server
```bash
uv run python app/main.py
```
The server will boot on `http://localhost:2001`, run database migrations automatically, and serve OpenAPI interactive documentation at `http://localhost:2001/docs`.
