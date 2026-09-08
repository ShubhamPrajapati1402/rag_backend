"""
Migration 001: Add document metadata columns and full-text search index.
"""
from sqlalchemy import Connection, text


def upgrade(conn: Connection) -> None:
    conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);"))
    conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;"))
    conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_path TEXT;"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_doc_chunks_fts ON document_chunks USING gin(to_tsvector('english', text_content));"))
