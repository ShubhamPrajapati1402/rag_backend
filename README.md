# RAG Application Backend

This is the backend for a Retrieval-Augmented Generation (RAG) application. It handles PDF document uploading, processing, embedding generation, vector storage, and query handling using Large Language Models.

## Tech Stack

* **Web Framework:** FastAPI (running on Uvicorn)
* **Database ORM:** SQLAlchemy (with `pgvector` extension)
* **Database & Vector Store:** Supabase Cloud (PostgreSQL)
* **RAG Framework:** LangChain & LangGraph (for Agentic RAG)
* **Embeddings:** Hugging Face API
* **Large Language Model (LLM):** Groq API
* **Document Parsing & OCR:** `unstructured`, `pytesseract`, `pdfplumber`
* **Logging:** `loguru`
* **Package Management & Virtual Environment:** `uv`

## Folder Structure

The project follows an industry-standard backend architecture:

```text
rag_backend/
├── app/
│   ├── api/          # API routers (e.g., PDF upload endpoint)
│   ├── core/         # App configuration and environment variables
│   ├── db/           # Supabase connection setup and pgvector session
│   ├── models/       # Pydantic models (Schemas for request/responses)
│   ├── services/     # Business logic (PDF parsing, embeddings generation)
│   └── utils/        # Helper functions
├── data/
│   └── uploads/      # Temporary storage for uploaded source PDFs
└── tests/            # Unit and integration tests
```

## Setup Instructions

### 1. Prerequisites
Make sure you have [Python](https://www.python.org/downloads/) and [`uv`](https://github.com/astral-sh/uv) installed on your system. 

### 2. Activate Virtual Environment
The virtual environment has already been created. To activate it on Windows, run:
```powershell
.venv\Scripts\activate
```

### 3. Environment Variables
1. Copy the `.env.example` file and rename it to `.env`:
   ```powershell
   cp .env.example .env
   ```
2. Open the `.env` file and fill in your configuration:
   * **Groq API Key:** Get it from the [Groq Console](https://console.groq.com/keys)
   * **Groq Model Name:** Set to `llama3-8b-8192` (or your preferred model)
   * **Hugging Face Token:** Get it from your [Hugging Face Settings](https://huggingface.co/settings/tokens)
   * **Hugging Face Model:** Set to `sentence-transformers/all-MiniLM-L6-v2` (or your preferred model)
   * **Supabase Connection (URI):** Click "Connect" on your Supabase dashboard and copy the Direct Connection URI.
   * **Supabase URL & Key:** Found under Configuration -> API Keys (use the Secret key for the backend).
   * **Supabase JWT Secret:** Found under Configuration -> JWT Keys (useful if implementing auth later).

### 4. Running the Application
*(Instructions will be added here once the main API server is implemented)*
