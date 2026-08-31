from fastapi import APIRouter
from app.api.routes import auth, chat, ingest, evaluation

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(ingest.router)
api_router.include_router(evaluation.router)
