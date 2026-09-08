"""
Migration 002: Add model provider and model name columns to chat sessions and messages.
"""
from sqlalchemy import Connection, text


def upgrade(conn: Connection) -> None:
    conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS model_provider VARCHAR(50) DEFAULT 'inbuilt';"))
    conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS model_name VARCHAR(100);"))
    conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS model_provider VARCHAR(50);"))
    conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS model_name VARCHAR(100);"))
