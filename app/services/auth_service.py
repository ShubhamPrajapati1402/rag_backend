from typing import Optional, Tuple, Any
from loguru import logger
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, BackgroundTasks

from app.models.user import User
from app.schemas.user import UserSignupRequest, UserLoginRequest, OTPVerifyRequest, OTPResendRequest
from app.core.config import settings
from app.core.security import get_password_hash, verify_password, create_access_token
from app.services.otp_service import OTPService
from app.services.email_service import EmailService
from app.services.google_auth_service import GoogleAuthService

class AuthService:
    @staticmethod
    def _is_bootstrap_developer(email: str) -> bool:
        dev_emails = [e.strip().lower() for e in settings.DEVELOPER_EMAILS.split(",") if e.strip()]
        return email.strip().lower() in dev_emails

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email.strip().lower()).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @classmethod
    async def signup(
        cls,
        db: Session,
        signup_data: UserSignupRequest,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> User:
        """
        Handles initial registration by saving unverified user and sending a Redis-backed OTP asynchronously.
        """
        email = signup_data.email.strip().lower()
        existing_user = cls.get_user_by_email(db, email)

        if existing_user and existing_user.is_verified:
            logger.warning(f"Signup rejected: Email {email} is already registered and verified.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered. Please log in."
            )

        # Check OTP rate limits (cooldown, hourly limits, lockout)
        OTPService.check_request_rate_limit(email, purpose="signup")

        if existing_user and not existing_user.is_verified:
            # Update credentials for pending user
            existing_user.hashed_password = get_password_hash(signup_data.password)
            if signup_data.full_name:
                existing_user.full_name = signup_data.full_name
            db.commit()
            db.refresh(existing_user)
            user = existing_user
            logger.info(f"Updated pending unverified account for {email}")
        else:
            # Create new unverified user record
            user = User(
                email=email,
                hashed_password=get_password_hash(signup_data.password),
                full_name=signup_data.full_name,
                auth_provider="local",
                is_verified=False,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created new unverified account for {email}")

        # Generate and store OTP in Redis
        otp_code = OTPService.generate_otp_code()
        OTPService.store_otp(email, otp_code, purpose="signup")

        # Dispatch email non-blockingly in background
        if background_tasks:
            background_tasks.add_task(EmailService.send_otp_email, email, otp_code, user.full_name)
        else:
            await EmailService.send_otp_email(email, otp_code, user.full_name)

        return user

    @classmethod
    async def verify_signup_otp(
        cls,
        db: Session,
        verify_data: OTPVerifyRequest,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Tuple[User, str]:
        """
        Verifies submitted OTP code against Redis, activates user, creates JWT session,
        and sends a Welcome Email non-blockingly in background.
        """
        email = verify_data.email.strip().lower()
        user = cls.get_user_by_email(db, email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found."
            )

        # Verify against Redis (handles attempts, invalidation, and lockout)
        OTPService.verify_otp(email, verify_data.otp_code, purpose="signup")

        # Activate user in database
        user.is_verified = True
        if cls._is_bootstrap_developer(user.email):
            user.is_superuser = True
        db.commit()
        db.refresh(user)

        # Send rich Welcome Email in background
        if background_tasks:
            background_tasks.add_task(EmailService.send_welcome_email, user.email, user.full_name)
        else:
            await EmailService.send_welcome_email(user.email, user.full_name)

        # Generate JWT session token
        token = create_access_token(
            subject=user.id,
            claims={"email": user.email, "auth_provider": user.auth_provider}
        )

        logger.info(f"User {email} successfully verified via OTP and logged in.")
        return user, token

    @classmethod
    async def resend_signup_otp(
        cls,
        db: Session,
        resend_data: OTPResendRequest,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> None:
        """
        Resends an OTP to an unverified user respecting cooldowns and rate limits.
        """
        email = resend_data.email.strip().lower()
        user = cls.get_user_by_email(db, email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found."
            )

        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is already verified. Please log in."
            )

        # Enforce rate limits
        OTPService.check_request_rate_limit(email, purpose="signup")

        # Generate, store in Redis, and dispatch OTP in background
        otp_code = OTPService.generate_otp_code()
        OTPService.store_otp(email, otp_code, purpose="signup")
        
        if background_tasks:
            background_tasks.add_task(EmailService.send_otp_email, email, otp_code, user.full_name)
        else:
            await EmailService.send_otp_email(email, otp_code, user.full_name)

        logger.info(f"Resent OTP to {email}")

    @classmethod
    async def login(
        cls,
        db: Session,
        login_data: UserLoginRequest,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Tuple[User, str]:
        """
        Authenticates user credentials and checks active/verified status.
        """
        email = login_data.email.strip().lower()
        user = cls.get_user_by_email(db, email)

        if not user or not user.hashed_password or not verify_password(login_data.password, user.hashed_password):
            logger.warning(f"Failed login attempt for {email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated. Please contact support."
            )

        if not user.is_verified:
            # Trigger fresh OTP to help unverified user complete signup
            try:
                OTPService.check_request_rate_limit(email, purpose="signup")
                otp_code = OTPService.generate_otp_code()
                OTPService.store_otp(email, otp_code, purpose="signup")
                if background_tasks:
                    background_tasks.add_task(EmailService.send_otp_email, email, otp_code, user.full_name)
                else:
                    await EmailService.send_otp_email(email, otp_code, user.full_name)
            except Exception:
                pass  # Cooldown might be active

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not verified. A new verification code has been sent to your email."
            )

        if cls._is_bootstrap_developer(user.email) and not user.is_superuser:
            user.is_superuser = True
            db.commit()
            db.refresh(user)

        token = create_access_token(
            subject=user.id,
            claims={"email": user.email, "auth_provider": user.auth_provider}
        )

        logger.info(f"User {email} logged in successfully.")
        return user, token

    @classmethod
    async def authenticate_google(
        cls,
        db: Session,
        google_data: Any,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Tuple[User, str]:
        """
        Verifies Google OAuth2 ID token, finds or creates verified user, and creates JWT session.
        Sends a Welcome Email if this is a first-time signup.
        """
        raw_token = google_data.id_token if hasattr(google_data, "id_token") else str(google_data)
        google_payload = GoogleAuthService.verify_token(raw_token)
        email = google_payload["email"].strip().lower()
        full_name = google_payload.get("name")
        avatar_url = google_payload.get("picture")

        user = cls.get_user_by_email(db, email)
        is_new_user = False

        if user:
            # Link or update existing account
            if not user.is_verified:
                user.is_verified = True
                is_new_user = True
            # Always sync Google profile image, full name, and provider
            if avatar_url:
                user.avatar_url = avatar_url
            if full_name:
                user.full_name = full_name
            user.auth_provider = "google"
            if cls._is_bootstrap_developer(user.email) and not user.is_superuser:
                user.is_superuser = True
            
            # Keep user.hashed_password completely intact so the user can login with either method!
            db.commit()
            db.refresh(user)
            logger.info(f"Existing user {email} synced profile, updated auth_provider to google, and authenticated via Google OAuth")
        else:
            # Create new user pre-verified via Google
            user = User(
                email=email,
                hashed_password=None,
                full_name=full_name,
                avatar_url=avatar_url,
                auth_provider="google",
                is_verified=True,
                is_active=True,
                is_superuser=cls._is_bootstrap_developer(email)
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            is_new_user = True
            logger.info(f"Created new verified user for {email} via Google OAuth")

        # Send welcome email for newly onboarded user
        if is_new_user:
            if background_tasks:
                background_tasks.add_task(EmailService.send_welcome_email, user.email, user.full_name)
            else:
                await EmailService.send_welcome_email(user.email, user.full_name)

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated."
            )

        token = create_access_token(
            subject=user.id,
            claims={"email": user.email, "auth_provider": user.auth_provider}
        )

        return user, token
