from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import Base, User, Document, DocumentChunk, ChatSession, ChatMessage

# SQLAlchemy 2.0 requires "postgresql://" instead of "postgres://"
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Set up the SQLAlchemy engine with optimized connection pooling
engine = create_engine(
    db_url,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_timeout=10,
    connect_args={"connect_timeout": 5}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency function to generate and yield a new database session for each API request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from app.db.migrations.runner import run_migrations

def init_db():
    """
    Initializes the database by creating all tables defined in SQLAlchemy models
    and executing version-tracked schema migrations.
    """
    try:
        # 1. Ensure core schema tables exist
        Base.metadata.create_all(bind=engine)
        
        # 2. Run version-tracked schema migrations
        run_migrations(engine)
        
        logger.info("Database tables initialized and migrated successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
