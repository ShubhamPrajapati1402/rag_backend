import sys
from pathlib import Path

# Ensure project root directory is in sys.path when running app/main.py directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import uvicorn

from app.core.config import settings
from app.db.session import init_db
from app.api.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler to perform startup and shutdown tasks.
    """
    logger.info(f"Starting RAG Backend on port {settings.BACKEND_PORT}...")
    try:
        init_db()
    except Exception as e:
        logger.error(f"Database initialization warning on startup: {e}")
    yield
    logger.info("Shutting down RAG Backend...")

app = FastAPI(
    title="RAG Application API",
    description="Production-grade Agentic RAG Backend with JWT & HttpOnly Cookie Authentication, Redis OTP Engine, and Multi-Format Ingestion",
    version="1.0.0",
    lifespan=lifespan
)

# Configure Cross-Origin Resource Sharing (CORS) with support for credentials/cookies
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(api_router)

@app.get("/health", tags=["Health"])
def health_check():
    """
    Service health check endpoint.
    """
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "port": settings.BACKEND_PORT
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG
    )
