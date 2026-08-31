from typing import List, Optional, Union
import json
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Settings class to securely load and validate all environment variables from the .env file.
    No static defaults or fallbacks are used for critical secrets, ports, or API endpoints.
    """
    # Database
    DATABASE_URL: str
    
    # LLM
    GROQ_API_KEY: str
    GROQ_MODEL_NAME: str
    GEMINI_API_KEY: str
    GEMINI_MODEL_NAME: str
    
    # Embeddings & Reranking
    HUGGINGFACE_API_KEY: str
    HUGGINGFACE_EMBEDDING_MODEL: str
    HUGGINGFACE_RERANKER_MODEL: str
    EMBEDDING_MAX_WORKERS: int
    DOCUMENT_LEASE_MINUTES: int 
    
    # PDF Parsing
    PDF_PARSING_STRATEGY: str
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_JWT_SECRET: Optional[str] = None
    
    # Server & CORS
    BACKEND_HOST: str
    BACKEND_PORT: int
    FRONTEND_URL: str
    CORS_ORIGINS: Union[List[str], str]
    
    # Authentication & JWT Security
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    DEVELOPER_EMAILS: str = "scprajapati14@gmail.com"
    
    # Cookie Configuration (HttpOnly Sessions)
    COOKIE_NAME: str
    COOKIE_SECURE: bool
    COOKIE_SAMESITE: str
    COOKIE_DOMAIN: Optional[str] = None
    
    # Redis & OTP
    REDIS_URL: str
    OTP_LENGTH: int
    OTP_EXPIRE_SECONDS: int
    
    # OTP Rate Limiting & Restrictions
    OTP_RESEND_COOLDOWN_SECONDS: int
    OTP_MAX_REQUESTS_PER_HOUR: int
    OTP_MAX_VERIFY_ATTEMPTS: int
    OTP_LOCKOUT_SECONDS: int
    
    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    
    # Email (SMTP)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None
    EMAILS_FROM_NAME: Optional[str] = None
    
    # App Settings
    ENVIRONMENT: str
    DEBUG: bool

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[List[str], str]) -> List[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    return json.loads(v_stripped)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Instantiate a global settings object that can be imported across the application
settings = Settings()
