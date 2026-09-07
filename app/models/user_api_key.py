from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.document import Base

class UserAPIKey(Base):
    """
    SQLAlchemy model representing the 'user_api_keys' table.
    Stores AES-256 encrypted personal API keys for custom providers (BYOK).
    """
    __tablename__ = "user_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # "gemini", "groq", "openai", "anthropic", "deepseek", "mistral", "openrouter", "custom"
    encrypted_key = Column(Text, nullable=False)
    key_hint = Column(String(50), nullable=False)  # Masked preview, e.g. "sk-...a1b2"
    base_url = Column(String(500), nullable=True)   # Optional custom endpoint (e.g. for Ollama, vLLM, DeepSeek, OpenRouter)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        onupdate=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_provider_key"),
    )

    def __repr__(self):
        return f"<UserAPIKey(id={self.id}, user_id={self.user_id}, provider='{self.provider}', hint='{self.key_hint}', active={self.is_active})>"
