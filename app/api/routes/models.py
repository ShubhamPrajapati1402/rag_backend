from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

from app.db.session import get_db
from app.models.user import User
from app.models.user_api_key import UserAPIKey
from app.api.deps import get_current_user, get_optional_current_user
from app.core.crypto import encrypt_secret, mask_api_key
from app.services.rag.llm import validate_model_connection
from app.schemas.model_schemas import (
    ModelInfo,
    ProviderInfo,
    ModelsCatalogResponse,
    UserAPIKeyCreate,
    UserAPIKeyResponse,
    TestConnectionRequest,
    TestConnectionResponse
)

router = APIRouter(prefix="/models", tags=["Model Providers & BYOK Vault"])

# Full catalog metadata of built-in and supported BYOK providers
CATALOG_DEFINITIONS = [
    {
        "provider": "inbuilt",
        "name": "Noesis Inbuilt (Free & Resilient)",
        "description": "Zero configuration multi-tier fallback chain (Google Gemini 2.5 Flash + Groq fallback). Managed directly by backend servers.",
        "website_url": "https://ai.google.dev",
        "api_key_help_url": "",
        "default_base_url": None,
        "is_inbuilt": True,
        "models": [
            {
                "id": "gemini-2.5-flash",
                "name": "Gemini 2.5 Flash (Inbuilt Default)",
                "description": "Ultra-low latency primary engine with automatic failover to Groq.",
                "context_window": 1048576,
                "is_inbuilt": True,
                "requires_api_key": False
            }
        ]
    },
    {
        "provider": "gemini",
        "name": "Google Gemini",
        "description": "Google's state-of-the-art multimodal reasoning models with 1M+ token context windows.",
        "website_url": "https://ai.google.dev",
        "api_key_help_url": "https://aistudio.google.com/app/apikey",
        "default_base_url": None,
        "is_inbuilt": False,
        "models": [
            {
                "id": "gemini-2.5-flash",
                "name": "Gemini 2.5 Flash",
                "description": "High frequency, low latency reasoning.",
                "context_window": 1048576,
                "is_inbuilt": False,
                "requires_api_key": True
            },
            {
                "id": "gemini-2.5-pro",
                "name": "Gemini 2.5 Pro",
                "description": "Deep multi-step analytical reasoning and complex synthesis.",
                "context_window": 2097152,
                "is_inbuilt": False,
                "requires_api_key": True
            },
            {
                "id": "gemini-1.5-pro",
                "name": "Gemini 1.5 Pro",
                "description": "Massive context document comprehension.",
                "context_window": 2097152,
                "is_inbuilt": False,
                "requires_api_key": True
            }
        ]
    },
    {
        "provider": "groq",
        "name": "Groq LPU Inference",
        "description": "Ultra-high speed Language Processing Units (LPU) serving open-source foundation models at 500+ tokens/sec.",
        "website_url": "https://groq.com",
        "api_key_help_url": "https://console.groq.com/keys",
        "default_base_url": None,
        "is_inbuilt": False,
        "models": [
            {
                "id": "llama-3.3-70b-versatile",
                "name": "Llama 3.3 70B Versatile",
                "description": "Meta's flagship open-weights model on Groq hardware.",
                "context_window": 131072,
                "is_inbuilt": False,
                "requires_api_key": True
            },
            {
                "id": "qwen/qwen3.8-27b",
                "name": "Qwen 2.5 72B / 27B",
                "description": "Exceptional coding, math, and multilingual reasoning.",
                "context_window": 131072,
                "is_inbuilt": False,
                "requires_api_key": True
            },
            {
                "id": "deepseek-r1-distill-llama-70b",
                "name": "DeepSeek R1 Distill 70B",
                "description": "Fast reasoning distillation powered by Groq LPU.",
                "context_window": 131072,
                "is_inbuilt": False,
                "requires_api_key": True
            }
        ]
    },
    {
        "provider": "openai",
        "name": "OpenAI",
        "description": "Industry benchmark models including GPT-4o, GPT-4o Mini, and reasoning models.",
        "website_url": "https://openai.com",
        "api_key_help_url": "https://platform.openai.com/api-keys",
        "default_base_url": "https://api.openai.com/v1",
        "is_inbuilt": False,
        "models": [
            {
                "id": "gpt-4o",
                "name": "GPT-4o (Omni)",
                "description": "Flagship high-intelligence multimodal model.",
                "context_window": 128000,
                "is_inbuilt": False,
                "requires_api_key": True
            },
            {
                "id": "gpt-4o-mini",
                "name": "GPT-4o Mini",
                "description": "Affordable, fast, lightweight model for everyday tasks.",
                "context_window": 128000,
                "is_inbuilt": False,
                "requires_api_key": True
            },
            {
                "id": "o3-mini",
                "name": "o3-mini",
                "description": "Next-gen cost-efficient STEM reasoning model.",
                "context_window": 200000,
                "is_inbuilt": False,
                "requires_api_key": True
            }
        ]
    },
    {
        "provider": "anthropic",
        "name": "Anthropic Claude",
        "description": "Claude 3.5 Sonnet and Haiku — world leaders in nuanced writing, complex coding, and safe tool use.",
        "website_url": "https://anthropic.com",
        "api_key_help_url": "https://console.anthropic.com/settings/keys",
        "default_base_url": None,
        "is_inbuilt": False,
        "models": [
            {
                "id": "claude-3-5-sonnet-latest",
                "name": "Claude 3.5 Sonnet",
                "description": "Benchmark-leading intelligence and natural conversational tone.",
                "context_window": 200000,
                "is_inbuilt": False,
                "requires_api_key": True
            },
            {
                "id": "claude-3-5-haiku-latest",
                "name": "Claude 3.5 Haiku",
                "description": "Lightning-fast responsiveness with near-frontier capability.",
                "context_window": 200000,
                "is_inbuilt": False,
                "requires_api_key": True
            }
        ]
    },
    {
        "provider": "deepseek",
        "name": "DeepSeek AI",
        "description": "DeepSeek-V3 and DeepSeek-R1 reasoning models via official OpenAI-compatible API.",
        "website_url": "https://deepseek.com",
        "api_key_help_url": "https://platform.deepseek.com/api_keys",
        "default_base_url": "https://api.deepseek.com/v1",
        "is_inbuilt": False,
        "models": [
            {
                "id": "deepseek-chat",
                "name": "DeepSeek V3 (Chat)",
                "description": "Versatile general-purpose flagship model.",
                "context_window": 64000,
                "is_inbuilt": False,
                "requires_api_key": True
            },
            {
                "id": "deepseek-reasoner",
                "name": "DeepSeek R1 (Reasoner)",
                "description": "Open reasoning model with chain-of-thought verification.",
                "context_window": 64000,
                "is_inbuilt": False,
                "requires_api_key": True
            }
        ]
    },
    {
        "provider": "mistral",
        "name": "Mistral AI",
        "description": "Leading European open & commercial models (Mistral Large, Codestral).",
        "website_url": "https://mistral.ai",
        "api_key_help_url": "https://console.mistral.ai/api-keys",
        "default_base_url": "https://api.mistral.ai/v1",
        "is_inbuilt": False,
        "models": [
            {
                "id": "mistral-large-latest",
                "name": "Mistral Large 2",
                "description": "Top-tier reasoning, code, and multilingual tasks.",
                "context_window": 128000,
                "is_inbuilt": False,
                "requires_api_key": True
            },
            {
                "id": "codestral-latest",
                "name": "Codestral",
                "description": "State-of-the-art coding and software synthesis.",
                "context_window": 32000,
                "is_inbuilt": False,
                "requires_api_key": True
            }
        ]
    },
    {
        "provider": "openrouter",
        "name": "OpenRouter",
        "description": "Unified API gateway offering access to 100+ models from all major providers.",
        "website_url": "https://openrouter.ai",
        "api_key_help_url": "https://openrouter.ai/keys",
        "default_base_url": "https://openrouter.ai/api/v1",
        "is_inbuilt": False,
        "models": [
            {
                "id": "openrouter/auto",
                "name": "OpenRouter Auto Router",
                "description": "Automatically picks the highest quality/price model.",
                "context_window": 128000,
                "is_inbuilt": False,
                "requires_api_key": True
            },
            {
                "id": "meta-llama/llama-3.3-70b-instruct",
                "name": "Llama 3.3 70B (OpenRouter)",
                "description": "High performance Llama 3.3 through OpenRouter.",
                "context_window": 131072,
                "is_inbuilt": False,
                "requires_api_key": True
            }
        ]
    },
    {
        "provider": "custom",
        "name": "Custom / Local Endpoint (Ollama, vLLM)",
        "description": "Connect any local or custom OpenAI-compatible server (e.g. Ollama, LocalAI, vLLM, LM Studio).",
        "website_url": "https://ollama.com",
        "api_key_help_url": "",
        "default_base_url": "http://localhost:11434/v1",
        "is_inbuilt": False,
        "models": [
            {
                "id": "llama3.2",
                "name": "Local Ollama Llama 3.2",
                "description": "Local offline model via Ollama.",
                "context_window": 128000,
                "is_inbuilt": False,
                "requires_api_key": False
            }
        ]
    }
]


@router.get("", response_model=ModelsCatalogResponse, summary="List all supported models and provider configuration status")
def get_models_catalog(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Returns the comprehensive catalog of all available models.
    If authenticated, indicates which providers the user has actively configured with personal keys.
    """
    user_configured_providers = set()
    if current_user:
        keys = db.query(UserAPIKey.provider).filter(
            UserAPIKey.user_id == current_user.id,
            UserAPIKey.is_active == True
        ).all()
        user_configured_providers = {k[0] for k in keys}

    catalog_providers = []
    for p in CATALOG_DEFINITIONS:
        prov_id = p["provider"]
        is_conf = (prov_id == "inbuilt") or (prov_id in user_configured_providers)
        
        models_list = []
        for m in p["models"]:
            models_list.append(
                ModelInfo(
                    id=m["id"],
                    name=m["name"],
                    provider=prov_id,
                    description=m["description"],
                    context_window=m["context_window"],
                    is_inbuilt=m["is_inbuilt"],
                    requires_api_key=m["requires_api_key"],
                    is_configured=is_conf,
                    default_base_url=p.get("default_base_url")
                )
            )

        catalog_providers.append(
            ProviderInfo(
                provider=prov_id,
                name=p["name"],
                description=p["description"],
                website_url=p["website_url"],
                api_key_help_url=p["api_key_help_url"],
                default_base_url=p.get("default_base_url"),
                is_inbuilt=p["is_inbuilt"],
                is_configured=is_conf,
                models=models_list
            )
        )

    return ModelsCatalogResponse(
        providers=catalog_providers,
        default_model="gemini-2.5-flash",
        default_provider="inbuilt"
    )


@router.get("/keys", response_model=List[UserAPIKeyResponse], summary="List user's configured BYOK keys (Masked)")
def list_user_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists the authenticated user's configured provider keys.
    Returns safe masked hints (sk-...1234) with zero plaintext exposure.
    """
    keys = db.query(UserAPIKey).filter(
        UserAPIKey.user_id == current_user.id
    ).order_by(UserAPIKey.created_at.desc()).all()

    return [
        UserAPIKeyResponse(
            id=k.id,
            provider=k.provider,
            key_hint=k.key_hint,
            base_url=k.base_url,
            is_active=k.is_active,
            created_at=k.created_at,
            updated_at=k.updated_at
        )
        for k in keys
    ]


@router.post("/keys", response_model=UserAPIKeyResponse, summary="Save or update an encrypted API key for a provider")
def save_user_api_key(
    payload: UserAPIKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Stores or updates an API key for a model provider.
    Encrypts the key at rest using AES-256 Fernet.
    """
    clean_provider = payload.provider.strip().lower()
    clean_key = payload.api_key.strip()
    clean_url = payload.base_url.strip() if payload.base_url else None

    if not clean_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API Key cannot be empty."
        )

    encrypted = encrypt_secret(clean_key)
    masked = mask_api_key(clean_key)

    existing_key = db.query(UserAPIKey).filter(
        UserAPIKey.user_id == current_user.id,
        UserAPIKey.provider == clean_provider
    ).first()

    if existing_key:
        existing_key.encrypted_key = encrypted
        existing_key.key_hint = masked
        existing_key.base_url = clean_url
        existing_key.is_active = True
        db.commit()
        db.refresh(existing_key)
        saved_record = existing_key
        logger.info(f"[BYOKVault] Updated key for user_id={current_user.id}, provider='{clean_provider}'")
    else:
        new_key = UserAPIKey(
            user_id=current_user.id,
            provider=clean_provider,
            encrypted_key=encrypted,
            key_hint=masked,
            base_url=clean_url,
            is_active=True
        )
        db.add(new_key)
        db.commit()
        db.refresh(new_key)
        saved_record = new_key
        logger.info(f"[BYOKVault] Stored new key for user_id={current_user.id}, provider='{clean_provider}'")

    return UserAPIKeyResponse(
        id=saved_record.id,
        provider=saved_record.provider,
        key_hint=saved_record.key_hint,
        base_url=saved_record.base_url,
        is_active=saved_record.is_active,
        created_at=saved_record.created_at,
        updated_at=saved_record.updated_at
    )


@router.delete("/keys/{provider}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an encrypted API key for a provider")
def delete_user_api_key(
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Permanently revokes and deletes a stored API key for the authenticated user.
    """
    clean_provider = provider.strip().lower()
    existing_key = db.query(UserAPIKey).filter(
        UserAPIKey.user_id == current_user.id,
        UserAPIKey.provider == clean_provider
    ).first()

    if not existing_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No configured key found for provider '{provider}'."
        )

    db.delete(existing_key)
    db.commit()
    logger.info(f"[BYOKVault] Revoked key for user_id={current_user.id}, provider='{clean_provider}'")
    return None


@router.post("/test-connection", response_model=TestConnectionResponse, summary="Test provider API key connection")
async def test_api_key_connection(
    payload: TestConnectionRequest,
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Tests live communication with a model provider using the supplied or vault-stored key.
    """
    user_id = current_user.id if current_user else None
    success, message, latency_ms = await validate_model_connection(
        provider=payload.provider,
        api_key=payload.api_key,
        base_url=payload.base_url,
        model_name=payload.model_name,
        user_id=user_id
    )

    return TestConnectionResponse(
        success=success,
        message=message,
        latency_ms=latency_ms,
        model_tested=payload.model_name
    )
