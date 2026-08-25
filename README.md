# RAG Application Backend

This is the backend for a Retrieval-Augmented Generation (RAG) application. It handles PDF document uploading, processing, embedding generation, vector storage, and query handling using Large Language Models.

## Tech Stack

* **Package Management & Virtual Environment:** `uv`
* **Embeddings:** Hugging Face API
* **Large Language Model (LLM):** Groq API
* **Database & Vector Store:** Supabase Cloud (PostgreSQL with `pgvector` extension)

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
2. Open the `.env` file and fill in your API keys:
   * **Groq API Key:** Get it from the [Groq Console](https://console.groq.com/keys)
   * **Hugging Face Token:** Get it from your [Hugging Face Settings](https://huggingface.co/settings/tokens)
   * **Supabase Database URL:** Get the Connection String (URI) from your Supabase Project settings.

### 4. Running the Application
*(Instructions will be added here once the main API server is implemented)*
