from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import bcrypt
import jwt
from fastapi import Response
from loguru import logger
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a bcrypt hashed password.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

def get_password_hash(password: str) -> str:
    """
    Generates a secure bcrypt hash for a given password.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def create_access_token(
    subject: Union[str, Any],
    claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Creates a signed JWT access token.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }
    if claims:
        to_encode.update(claims)
        
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates a JWT access token. Returns payload dict or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.PyJWTError as e:
        logger.debug(f"JWT decode error: {e}")
        return None

SESSION_COOKIE_HINT = "rag_logged_in"


def set_auth_cookie(response: Response, token: str) -> None:
    """
    Sets the secure HttpOnly cookie for auth as well as a non-HttpOnly
    companion session cookie so the frontend can detect active sessions without
    blindly making unauthenticated network requests.
    """
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    domain = settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None
    
    # 1. Secure HttpOnly cookie containing the actual JWT token
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        max_age=max_age,
        expires=max_age,
        path="/",
        domain=domain,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE.lower()
    )
    
    # 2. Non-HttpOnly companion cookie indicator for client-side session detection
    response.set_cookie(
        key=SESSION_COOKIE_HINT,
        value="1",
        max_age=max_age,
        expires=max_age,
        path="/",
        domain=domain,
        secure=settings.COOKIE_SECURE,
        httponly=False,
        samesite=settings.COOKIE_SAMESITE.lower()
    )


def delete_auth_cookie(response: Response) -> None:
    """
    Clears both the auth cookie and companion session cookie with immediate expiration.
    """
    domain = settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None
    
    # 1. Clear HttpOnly auth cookie
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        path="/",
        domain=domain,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE.lower()
    )
    
    # 2. Clear companion session cookie
    response.delete_cookie(
        key=SESSION_COOKIE_HINT,
        path="/",
        domain=domain,
        secure=settings.COOKIE_SECURE,
        httponly=False,
        samesite=settings.COOKIE_SAMESITE.lower()
    )

