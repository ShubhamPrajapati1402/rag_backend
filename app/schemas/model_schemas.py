from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class ModelInfo(BaseModel):
    id: str = Field(..., description="Unique model identifier, e.g. 'gpt-4o' or 'gemini-2.5-flash'")
    name: str = Field(..., description="Human readable model display name")
    provider: str = Field(..., description="Provider name: 'inbuilt', 'gemini', 'groq', 'openai', 'anthropic', 'deepseek', 'mistral', 'openrouter', 'custom'")
    description: str = Field("", description="Brief description of model strengths and capabilities")
    context_window: int = Field(128000, description="Context window size in tokens")
    is_inbuilt: bool = Field(False, description="Whether this model uses system-managed credentials")
    requires_api_key: bool = Field(True, description="Whether the user needs to provide an API key")
    is_configured: bool = Field(False, description="Whether the authenticated user currently has an active key for this provider")
    default_base_url: Optional[str] = Field(None, description="Default API endpoint base URL if applicable")

class ProviderInfo(BaseModel):
    provider: str
    name: str
    description: str
    website_url: str
    api_key_help_url: str
    default_base_url: Optional[str] = None
    is_inbuilt: bool = False
    is_configured: bool = False
    models: List[ModelInfo] = []

class ModelsCatalogResponse(BaseModel):
    providers: List[ProviderInfo]
    default_model: str = "gemini-2.5-flash"
    default_provider: str = "inbuilt"

class UserAPIKeyCreate(BaseModel):
    provider: str = Field(..., description="Provider name ('gemini', 'groq', 'openai', 'anthropic', 'deepseek', 'mistral', 'openrouter', 'custom')")
    api_key: str = Field(..., min_length=3, description="Plaintext API key to be securely encrypted at rest")
    base_url: Optional[str] = Field(None, description="Optional custom base URL for self-hosted / compatible endpoints")

class UserAPIKeyResponse(BaseModel):
    id: int
    provider: str
    key_hint: str
    base_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

class TestConnectionRequest(BaseModel):
    provider: str = Field(..., description="Provider to test")
    api_key: Optional[str] = Field(None, description="API key to test. If omitted, tests the stored key from DB")
    base_url: Optional[str] = Field(None, description="Optional base URL for custom provider")
    model_name: Optional[str] = Field(None, description="Model to test invocation with")

class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    latency_ms: float
    model_tested: Optional[str] = None
