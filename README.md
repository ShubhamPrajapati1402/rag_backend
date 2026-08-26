# RAG Application Backend

This is the backend for a Retrieval-Augmented Generation (RAG) application. It handles PDF document uploading, processing, embedding generation, vector storage, and query handling using Large Language Models.

## Current State

The project currently implements the **Data Ingestion Pipeline**. It can process complex PDFs, extract text and tables, chunk the content logically, generate vector embeddings, and store them in a PostgreSQL database with pgvector. The FastAPI endpoints and LLM retrieval logic are planned for future development.

## Tech Stack

* **Web Framework:** FastAPI (Planned)
* **Database ORM:** SQLAlchemy (with `pgvector` extension)
* **Database & Vector Store:** Supabase Cloud (PostgreSQL)
* **Embeddings:** Hugging Face Inference API (`BAAI/bge-m3`)
* **Large Language Model (LLM):** Groq API (Planned)
* **RAG Framework:** LangChain & LangGraph
* **Document Parsing & OCR:** `unstructured` (hi_res strategy), `pytesseract`, `pdfplumber`
* **Logging:** `loguru`
* **Package Management:** `uv`

## Folder Structure

```text
rag_backend/
├── app/
│   ├── api/          # API routers (Planned)
│   ├── core/         # App configuration (Pydantic Settings)
│   ├── db/           # SQLAlchemy session setup and database connection
│   ├── models/       # Database models (e.g., DocumentChunk with Vector)
│   ├── scripts/      # Standalone scripts (e.g., ingest.py)
│   ├── services/     # Business logic (PDF parsing, embeddings generation)
│   └── utils/        # Helper functions
├── data/
│   └── uploads/      # Storage for source PDFs to be ingested
└── tests/            # Unit and integration tests
```

## Core Components

1. **Document Processor (`app/services/document_processor.py`)**: Uses the `unstructured` library to partition PDFs (handling complex layouts and tables via hi-res strategy) and chunks them by title.
2. **Embeddings Service (`app/services/embeddings.py`)**: Uses the `HuggingFaceInferenceAPIEmbeddings` from LangChain to convert text chunks into 1024-dimensional vectors without running the model locally.
3. **Database Models (`app/models/document.py`)**: Defines the `DocumentChunk` schema, storing chunk metadata, text, and the pgvector `embedding`.
4. **Ingestion Script (`app/scripts/ingest.py`)**: Orchestrates the pipeline—reading a PDF from `data/uploads`, processing it, fetching embeddings, and committing everything to Supabase.

## Setup Instructions

### 1. Prerequisites
Make sure you have [Python](https://www.python.org/downloads/) and [`uv`](https://github.com/astral-sh/uv) installed on your system. 

### 2. Activate Virtual Environment
To activate the virtual environment on Windows, run:
```powershell
.venv\Scripts\activate
```

### 3. Environment Variables
1. Copy the `.env.example` file and rename it to `.env`:
   ```powershell
   cp .env.example .env
   ```
2. Open the `.env` file and fill in your configuration:
   * **Database URL:** Supabase PostgreSQL connection string (ensure it uses `postgresql://` instead of `postgres://`).
   * **Groq API Key:** Get it from the [Groq Console](https://console.groq.com/keys)
   * **Groq Model Name:** e.g., `llama3-8b-8192`
   * **Hugging Face Token:** Get it from your [Hugging Face Settings](https://huggingface.co/settings/tokens)
   * **Hugging Face Model:** Set to `BAAI/bge-m3`
   * **Supabase Credentials:** Optional API keys if directly integrating with Supabase's REST API.

### 4. Running the Ingestion Pipeline

To ingest a PDF into your vector database, place it in the `data/uploads/` directory and update the target file path in `app/scripts/ingest.py` (bottom of the file). Then run:

```powershell
python app/scripts/ingest.py
```
This will:
1. Parse and chunk the PDF using `unstructured`.
2. Call the Hugging Face API to generate vector embeddings.
3. Save the chunks and vectors to your Supabase PostgreSQL database.
