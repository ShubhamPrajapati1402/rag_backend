"""
Database Schema Migration Runner.

Automatically tracks and runs versioned database migrations on backend startup.
If the database schema is already up to date, pending migrations are skipped instantly.
"""
from typing import Callable, List, Tuple
from sqlalchemy import Engine, text
from loguru import logger

from app.db.migrations import (
    m001_initial_metadata,
    m002_chat_session_models,
    m003_upgrade_gemini_models,
)

# Ordered registry of all schema migrations
MIGRATION_REGISTRY: List[Tuple[str, str, Callable]] = [
    ("001_initial_metadata", "Add document metadata columns and full-text search index", m001_initial_metadata.upgrade),
    ("002_chat_session_models", "Add chat session model metadata columns", m002_chat_session_models.upgrade),
    ("003_upgrade_gemini_models", "Upgrade legacy Gemini model references in chat sessions", m003_upgrade_gemini_models.upgrade),
]


def run_migrations(engine: Engine) -> None:
    """
    Checks the schema_migrations tracking table and applies any pending migrations in sequential order.
    """
    try:
        with engine.begin() as conn:
            # 1. Ensure the schema_migrations tracking table exists
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(100) PRIMARY KEY,
                    description TEXT,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # 2. Query all previously applied migration versions
            result = conn.execute(text("SELECT version FROM schema_migrations;"))
            applied_versions = {row[0] for row in result.fetchall()}

            # 3. Apply any unapplied migrations
            pending_count = 0
            for version, description, upgrade_fn in MIGRATION_REGISTRY:
                if version not in applied_versions:
                    logger.info(f"[Migrations] Applying migration '{version}' ({description})...")
                    upgrade_fn(conn)
                    conn.execute(
                        text("INSERT INTO schema_migrations (version, description) VALUES (:version, :description);"),
                        {"version": version, "description": description}
                    )
                    pending_count += 1
                else:
                    logger.debug(f"[Migrations] Skipping already applied migration '{version}'.")

            if pending_count > 0:
                logger.info(f"[Migrations] Successfully applied {pending_count} pending migration(s). Database is up to date.")
            else:
                logger.info("[Migrations] Database schema is up to date. No pending migrations.")

    except Exception as e:
        logger.error(f"[Migrations] Failed to run database migrations: {e}")
        raise
