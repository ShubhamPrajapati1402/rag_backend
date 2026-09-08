"""
Migration 003: Upgrade legacy gemini-2.5-flash entries to current GEMINI_MODEL_NAME.
"""
from sqlalchemy import Connection, text
from app.core.config import settings


def upgrade(conn: Connection) -> None:
    current_model = settings.GEMINI_MODEL_NAME
    conn.execute(
        text("UPDATE chat_sessions SET model_name = :new_model WHERE model_name = 'gemini-2.5-flash' OR model_name IS NULL;"),
        {"new_model": current_model}
    )
    conn.execute(
        text("UPDATE chat_messages SET model_name = :new_model WHERE model_name = 'gemini-2.5-flash';"),
        {"new_model": current_model}
    )
