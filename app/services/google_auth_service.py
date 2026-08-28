from typing import Any, Dict, Optional
from loguru import logger
from google.oauth2 import id_token
from google.auth.transport import requests
from fastapi import HTTPException, status
from app.core.config import settings

class GoogleAuthService:
    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """
        Verifies the Google OAuth2 ID token using official Google public certificates.
        Returns the parsed token payload containing user email, name, picture, and Google sub ID.
        """
        try:
            # Prepare Google client ID audience check if configured
            audience = settings.GOOGLE_CLIENT_ID if settings.GOOGLE_CLIENT_ID else None
            
            # Verify the ID token signature and audience
            id_info = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                audience=audience
            )

            # Ensure email exists in token payload
            if "email" not in id_info:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google authentication token missing verified email address."
                )

            return id_info
        except ValueError as e:
            logger.warning(f"Google ID token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Google authentication token: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during Google token verification: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify Google token with authentication provider."
            )
