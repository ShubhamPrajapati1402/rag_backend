import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet
from app.core.config import settings

def _get_fernet_instance() -> Fernet:
    """
    Derives a deterministic 32-byte base64-encoded key from the application SECRET_KEY.
    """
    # Hash the SECRET_KEY to 32 bytes using SHA-256
    key_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    # URL-safe base64 encode for Fernet requirement
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)

def encrypt_secret(plain_text: str) -> str:
    """
    Encrypts a plaintext secret string using AES-256 CBC via Fernet.
    """
    if not plain_text:
        return ""
    f = _get_fernet_instance()
    encrypted_bytes = f.encrypt(plain_text.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")

def decrypt_secret(cipher_text: str) -> str:
    """
    Decrypts an encrypted ciphertext string back to plaintext.
    """
    if not cipher_text:
        return ""
    f = _get_fernet_instance()
    decrypted_bytes = f.decrypt(cipher_text.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")

def mask_api_key(plain_key: str) -> str:
    """
    Creates a secure, human-readable masked version of an API key for safe UI display.
    Example: 'sk-proj-1234567890abcdef' -> 'sk-...cdef'
    """
    if not plain_key:
        return ""
    clean_key = plain_key.strip()
    if len(clean_key) <= 8:
        return "****" + clean_key[-2:] if len(clean_key) > 2 else "****"
    
    # Check if has a prefix like sk- or AIza
    if clean_key.startswith("sk-"):
        prefix = "sk-..."
        suffix = clean_key[-4:]
        return f"{prefix}{suffix}"
    elif clean_key.startswith("gsk_"):
        prefix = "gsk_..."
        suffix = clean_key[-4:]
        return f"{prefix}{suffix}"
    elif clean_key.startswith("AIza"):
        prefix = "AIza..."
        suffix = clean_key[-4:]
        return f"{prefix}{suffix}"
    else:
        prefix = clean_key[:3] + "..."
        suffix = clean_key[-4:]
        return f"{prefix}{suffix}"
