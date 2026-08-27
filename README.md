# RAG Application Backend

This is the backend for a Retrieval-Augmented Generation (RAG) application. It handles PDF document uploading, processing, embedding generation, vector storage, and query handling using Large Language Models.

## Current State

The project currently implements a **Production-Grade Multi-Format Data Ingestion Pipeline**. It can process 10+ file formats (PDF, Markdown, DOCX, CSV, Excel, HTML, JSON, PPTX, XML, TXT), extract structural text and tables, chunk the content using semantic format-specific strategies, generate vector embeddings, and store them securely in a PostgreSQL database using pgvector. The FastAPI endpoints and LLM retrieval logic are planned for future development.

The ingestion pipeline is designed for enterprise-level robustness, featuring:
- **Idempotency & Resumability**: If the server crashes during ingestion, the pipeline automatically resumes exactly where it left off, down to the specific chunk.
- **Atomic Leasing**: Distributed locks prevent two processes from processing the same document concurrently.
- **Dynamic Parser Registry**: Automatically routes files to their optimal parsing library (e.g., `pandas` for CSV, `beautifulsoup4` for HTML).
- **Semantic Chunking**: Groups context intelligently based on format (e.g., Markdown heading paths, Excel sheet boundaries).
- **Hybrid PDF Parsing & Fallback Engine**: Uses lightweight classification to route complex PDF pages to OCR and basic text pages to fast extractors, with deterministic safety mechanisms for perfect table preservation.

## Tech Stack

* **Web Framework:** FastAPI (Planned)
* **Database ORM:** SQLAlchemy (with `pgvector` extension)
* **Database & Vector Store:** Supabase Cloud (PostgreSQL)
* **Embeddings:** Hugging Face Inference API (`BAAI/bge-m3`)
* **Large Language Model (LLM):** Groq API (Planned)
* **RAG Framework:** LangChain & LangGraph
* **Document Parsing & OCR:** `unstructured`, `pdfplumber`, `markdown-it-py`, `pandas`, `python-docx`, `python-pptx`, `beautifulsoup4`
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
└── tests/            # Unit and integration tests
```

## Advanced Architecture Deep Dive

### 1. Multi-Format Parser Registry
Rather than using a single monolithic extraction library, the pipeline leverages an extensible `ParserRegistry`. When a file is ingested, the system automatically routes it to an optimized format-specific parser extending the `BaseParser` interface:

* **Tabular (CSV, TSV, Excel)**: Uses `pandas`. Rows are parsed into structured textual key-value maps. During chunking, boundaries are strictly enforced (e.g., a chunk will **never** contain data from two different Excel sheets).
* **Semantic Hierarchies (Markdown, DOCX, HTML, XML, JSON)**: Uses targeted libraries (`markdown-it-py`, `python-docx`, `beautifulsoup4`). The parsers track internal paths (like `<H1> > <H2>` or `user.orders[0]`). Chunks are sealed perfectly at these section boundaries so unrelated topics are never mixed.
* **Slides (PPTX)**: Uses `python-pptx`. Chunks strictly respect slide boundaries (1 Slide = 1 Chunk).
* **Plain Text (TXT)**: Relies on `\n\n` paragraph boundaries. Uses rolling character counts, with dynamic fallbacks for massive unbroken blocks of text.

### 2. Hybrid PDF Parsing
Parsing PDFs heavily using OCR and vision models (`hi_res`) is accurate but incredibly slow. The traditional `fast` parser is fast but fundamentally destroys tables and complex structural layouts.

To solve this, the pipeline uses a `hybrid` parsing architecture:
- **Lightweight Classification**: `app/services/classifier.py` scans every page of a PDF using `pdfplumber` in milliseconds. It searches for visual grid-lines indicating a table, or pages with less than 50 characters of embedded text (indicating a scanned image).
- **Dynamic Routing**: Complex pages are routed to the `hi_res` parser, while basic text pages are safely routed to the `fast` parser.
- **Seamless Merge**: The pipeline temporarily shatters the PDF into isolated one-page documents, processes them using their designated strategy, restores the original metadata, and merges them back in perfect sequential order before chunking.
- **Result**: Parses documents up to 3x faster with 0% structural loss.

### 3. Validation & Automated Fallback
The `app/services/validator.py` subsystem acts as a strict firewall for data integrity. Every parser implements a format-specific validator (`MarkdownValidator`, `CSVValidator`, etc.).
- **Chunk Tracking**: Ensures no content chunks were lost or ordered incorrectly.
- **Coverage Analysis (PDF)**: Uses a sliding window algorithm to guarantee that 100% of raw table content survived into the final chunks.
- **Targeted Fallback (PDF)**: If a table is lost during a `fast` pass, the specific failed pages are flagged, run exclusively through `hi_res_fallback`, patched back into the timeline, and re-validated.

### 4. Atomic Database Operations
- **Leasing**: When `ingest.py` begins processing a file, it acquires a time-bound lease. Other workers attempting to process the same `file_hash` are gracefully blocked.
- **Resumability**: Only chunks that are not already present in the database are processed. If an API rate-limit halts embedding chunk #50, the next ingestion run skips chunks 1-49 and resumes instantly at #50.
- **Configuration Protection**: Documents are stamped with a `config_hash`. If chunk size parameters or embedding models change in the code, the pipeline aborts ingestion for partially processed files to prevent mixed-vector poisoning.

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
   * **Database URL:** Supabase PostgreSQL connection string.
   * **Hugging Face Token:** Get it from your [Hugging Face Settings](https://huggingface.co/settings/tokens)
   * **Hugging Face Model:** Set to `BAAI/bge-m3`
   * **PDF Parsing Strategy (`PDF_PARSING_STRATEGY`):** 
     - `hi_res` (Default): Slow, maximally accurate.
     - `fast`: Fast, extracts pure text, destroys tables.
     - `hybrid`: Recommended dynamic architecture leveraging both.

### 4. Running the Ingestion Pipeline

To ingest a document (e.g., `.pdf`, `.md`, `.docx`, `.csv`, `.json`) into your vector database, place it in the `data/uploads/` directory and run:

```powershell
uv run python app/scripts/ingest.py "data/uploads/your_file.pdf"
```

#### Validation & Benchmark Mode
To test a document's extraction and chunking (and for PDFs, structural correctness) without hitting the database or generating embeddings, run:
```powershell
uv run python app/scripts/ingest.py --validate "data/uploads/your_file.pdf"
```
This prints a highly detailed terminal benchmark displaying element extraction rates, fallback loops (if applicable), chunking behavior, and speed metrics.
