from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserSignupRequest,
    UserLoginRequest,
    GoogleAuthRequest,
    OTPVerifyRequest,
    OTPResendRequest,
    UserResponse,
    AuthMessageResponse,
    TokenResponse
)
from app.services.auth_service import AuthService
from app.core.security import set_auth_cookie, delete_auth_cookie
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post(
    "/signup",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account (dispatches 6-digit OTP in background)"
)
async def signup(
    signup_data: UserSignupRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Registers a new unverified user account and dispatches an OTP in the background.
    Responds instantaneously (< 30ms) without waiting for SMTP server latency.
    """
    user = await AuthService.signup(db, signup_data, background_tasks=background_tasks)
    return AuthMessageResponse(
        message="Signup initiated. A 6-digit verification code has been sent to your email.",
        email=user.email
    )

@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify 6-digit OTP code & start authenticated cookie session"
)
async def verify_otp(
    verify_data: OTPVerifyRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Validates the submitted OTP code from Redis with anti-bruteforce guards.
    On success, activates the user, dispatches a welcome email in the background, sets an HttpOnly session cookie, and returns user data.
    """
    user, token = await AuthService.verify_signup_otp(db, verify_data, background_tasks=background_tasks)
    set_auth_cookie(response, token)
    return TokenResponse(
        message="Email verified successfully. You are now logged in.",
        user=UserResponse.model_validate(user),
        access_token=token
    )

@router.post(
    "/resend-otp",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend verification code to email"
)
async def resend_otp(
    resend_data: OTPResendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Issues a new verification OTP in background respecting cooldown and rate limits.
    """
    await AuthService.resend_signup_otp(db, resend_data, background_tasks=background_tasks)
    return AuthMessageResponse(
        message="A fresh verification code has been sent to your email.",
        email=resend_data.email
    )

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with email & password"
)
async def login(
    login_data: UserLoginRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Authenticates user credentials. If verified, sets a secure HttpOnly session cookie.
    If unverified, sends a new OTP in background and prompts verification.
    """
    user, token = await AuthService.login(db, login_data, background_tasks=background_tasks)
    set_auth_cookie(response, token)
    return TokenResponse(
        message="Login successful.",
        user=UserResponse.model_validate(user),
        access_token=token
    )

@router.post(
    "/google",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Sign in or Sign up using Google OAuth2 ID Token"
)
async def google_auth(
    google_data: GoogleAuthRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Authenticates Google OAuth2 ID Token, automatically provisions/links user account,
    sends a welcome email in background on new registration, and sets an HttpOnly session cookie.
    """
    user, token = await AuthService.authenticate_google(db, google_data.id_token, background_tasks=background_tasks)
    set_auth_cookie(response, token)
    return TokenResponse(
        message="Google authentication successful.",
        user=UserResponse.model_validate(user),
        access_token=token
    )

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current logged-in user profile"
)
def get_me(
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns the profile data of the currently authenticated user using session cookies.
    """
    return UserResponse.model_validate(current_user)

@router.post(
    "/logout",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout & clear session cookies"
)
def logout(
    response: Response
):
    """
    Clears the HttpOnly authentication session cookie.
    """
    delete_auth_cookie(response)
    return AuthMessageResponse(
        message="Logged out successfully."
    )
