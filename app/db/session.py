from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.document import Base

# SQLAlchemy 2.0 requires "postgresql://" instead of "postgres://"
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Set up the SQLAlchemy engine. pool_pre_ping=True checks if the connection is still alive before using it.
engine = create_engine(db_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency function to generate and yield a new database session for each API request.
    It ensures that the database connection is safely closed after the request is finished,
    even if an error occurs during the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initializes the database by creating all tables defined in our SQLAlchemy models.
    If the tables already exist in Supabase, this function safely does nothing.
    """
    try:
        # This will create the table in Supabase if it doesn't exist yet
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
