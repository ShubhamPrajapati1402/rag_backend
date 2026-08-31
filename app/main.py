import os
import sys
from pathlib import Path

# Disable unstructured library telemetry and tracking to prevent network hangs on Windows
os.environ["SCARF_NO_ANALYTICS"] = "true"
os.environ["DO_NOT_TRACK"] = "true"

# Ensure project root directory is in sys.path when running app/main.py directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import uvicorn

from app.core.config import settings
from app.db.session import init_db
from app.api.router import api_router
from app.api.routes.ws import router as ws_router
from app.core.websocket_manager import ws_manager

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

    # Start Redis Pub/Sub listener for real-time WebSocket clustering
    pubsub_task = asyncio.create_task(ws_manager.start_pubsub_listener())
    
    yield

    # Clean shutdown of background task
    pubsub_task.cancel()
    logger.info("Shutting down RAG Backend...")

app = FastAPI(
    title="Noesis API",
    description="Noesis - Production-grade Agentic RAG Backend with JWT & HttpOnly Cookie Authentication, Redis OTP Engine, and Multi-Format Ingestion",
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

# Register API routes & WebSockets
app.include_router(api_router)
app.include_router(ws_router)

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
