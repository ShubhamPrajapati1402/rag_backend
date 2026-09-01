from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from loguru import logger

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Extracts the JWT access token from HttpOnly cookies (with fallback to Authorization Bearer header),
    validates the token, and loads the active user from the database.
    """
    token: Optional[str] = None

    # 1. Primary: Extract from HttpOnly session cookie
    if settings.COOKIE_NAME in request.cookies:
        token = request.cookies.get(settings.COOKIE_NAME)

    # 2. Fallback: Extract from Authorization Bearer header if cookie is absent
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. No session cookie or token provided.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Decode and validate JWT
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or is invalid. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id_str = payload.get("sub")
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload identifier.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Load user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user

def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Extracts the user if an authenticated token is present, or returns None if unauthenticated.
    """
    token: Optional[str] = None
    if settings.COOKIE_NAME in request.cookies:
        token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    try:
        user_id = int(payload.get("sub"))
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None

def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Ensures that the current user is active and verified.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive."
        )
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not verified. Please verify your email."
        )
    return current_user

def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Ensures that the current user has developer/superuser privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Developer/Admin access required."
        )
    return current_user
