from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Settings class to securely load and validate all environment variables from the .env file.
    If a required variable is missing in the .env file, Pydantic will safely raise an error upon startup,
    preventing silent failures later in the code.
    """
    # Database
    DATABASE_URL: str
    
    # LLM
    GROQ_API_KEY: str
    GROQ_MODEL_NAME: str
    
    # Embeddings
    HUGGINGFACE_API_KEY: str
    HUGGINGFACE_EMBEDDING_MODEL: str
    EMBEDDING_MAX_WORKERS: int
    DOCUMENT_LEASE_MINUTES: int 
    
    # PDF Parsing
    PDF_PARSING_STRATEGY: str = "hi_res"
    
    # Supabase APIs (Optional but good to have)
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    # Tell Pydantic to read from the .env file and ignore any extra variables it finds there
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Instantiate a global settings object that can be imported and used anywhere in the application
settings = Settings()
