import secrets
from typing import Tuple
from loguru import logger
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.redis_client import get_redis_client

class OTPService:
    @staticmethod
    def _get_keys(email: str, purpose: str):
        email_clean = email.strip().lower()
        return {
            "code": f"otp:code:{purpose}:{email_clean}",
            "cooldown": f"otp:cooldown:{purpose}:{email_clean}",
            "req_count": f"otp:req_count:{purpose}:{email_clean}",
            "attempts": f"otp:attempts:{purpose}:{email_clean}",
            "lockout": f"otp:lockout:{purpose}:{email_clean}"
        }

    @staticmethod
    def generate_otp_code() -> str:
        """
        Generates a secure cryptographically random numeric string of configured length.
        """
        digits = "0123456789"
        return "".join(secrets.choice(digits) for _ in range(settings.OTP_LENGTH))

    @classmethod
    def check_request_rate_limit(cls, email: str, purpose: str = "signup") -> None:
        """
        Enforces cooldown, hourly request cap, and lockout restrictions before issuing an OTP.
        Raises HTTPException with 429 status code if any rate limit is triggered.
        """
        keys = cls._get_keys(email, purpose)
        redis_client = get_redis_client()

        # 1. Check if user is locked out due to brute force
        lockout_ttl = redis_client.ttl(keys["lockout"])
        if lockout_ttl and lockout_ttl > 0:
            logger.warning(f"OTP request blocked: {email} is locked out for {lockout_ttl}s")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed verification attempts. Please try again in {lockout_ttl} seconds."
            )

        # 2. Check resend cooldown
        cooldown_ttl = redis_client.ttl(keys["cooldown"])
        if cooldown_ttl and cooldown_ttl > 0:
            logger.warning(f"OTP request blocked: {email} cooldown active ({cooldown_ttl}s remaining)")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {cooldown_ttl} seconds before requesting a new OTP."
            )

        # 3. Check hourly request limit
        current_reqs = redis_client.get(keys["req_count"])
        if current_reqs and int(current_reqs) >= settings.OTP_MAX_REQUESTS_PER_HOUR:
            req_ttl = redis_client.ttl(keys["req_count"])
            logger.warning(f"OTP request blocked: {email} exceeded hourly limit ({current_reqs}/{settings.OTP_MAX_REQUESTS_PER_HOUR})")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Hourly OTP request limit exceeded ({settings.OTP_MAX_REQUESTS_PER_HOUR} max). Try again in {req_ttl // 60 + 1} minutes."
            )

    @classmethod
    def store_otp(cls, email: str, otp_code: str, purpose: str = "signup") -> None:
        """
        Stores generated OTP in Redis with expiration TTL and activates cooldown/rate tracking.
        """
        keys = cls._get_keys(email, purpose)
        redis_client = get_redis_client()

        # Pipeline operations for atomic execution
        pipe = redis_client.pipeline()
        
        # Store OTP code with expiry
        pipe.set(keys["code"], otp_code, ex=settings.OTP_EXPIRE_SECONDS)
        
        # Set cooldown key
        pipe.set(keys["cooldown"], "1", ex=settings.OTP_RESEND_COOLDOWN_SECONDS)
        
        # Increment hourly request counter
        pipe.incr(keys["req_count"])
        
        # Reset failed attempts for fresh OTP
        pipe.delete(keys["attempts"])
        
        pipe.execute()

        # Ensure hourly request counter has a 1-hour TTL if newly created
        if redis_client.ttl(keys["req_count"]) < 0:
            redis_client.expire(keys["req_count"], 3600)

        logger.info(f"Generated and stored OTP for {email} (purpose: {purpose}, expires in {settings.OTP_EXPIRE_SECONDS}s)")

    @classmethod
    def verify_otp(cls, email: str, otp_code: str, purpose: str = "signup") -> Tuple[bool, str]:
        """
        Validates the submitted OTP against Redis with brute-force attempt tracking and lockout guards.
        """
        keys = cls._get_keys(email, purpose)
        redis_client = get_redis_client()

        # 1. Check if user is currently locked out
        lockout_ttl = redis_client.ttl(keys["lockout"])
        if lockout_ttl and lockout_ttl > 0:
            logger.warning(f"OTP verify blocked: {email} is locked out ({lockout_ttl}s remaining)")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account verification is locked due to too many failed attempts. Try again in {lockout_ttl} seconds."
            )

        # 2. Retrieve active OTP code
        stored_code = redis_client.get(keys["code"])
        if not stored_code:
            logger.warning(f"OTP verification failed: OTP expired or not found for {email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired or was not requested. Please request a new one."
            )

        # 3. Check code match
        if otp_code.strip() == stored_code.strip():
            # Success: cleanup active OTP and attempts
            redis_client.delete(keys["code"], keys["attempts"], keys["cooldown"])
            logger.info(f"OTP verified successfully for {email}")
            return True, "OTP verified successfully."

        # 4. Handle mismatch & increment attempts
        attempts = redis_client.incr(keys["attempts"])
        if redis_client.ttl(keys["attempts"]) < 0:
            redis_client.expire(keys["attempts"], settings.OTP_EXPIRE_SECONDS)

        logger.warning(f"Incorrect OTP submitted for {email}. Failed attempts: {attempts}/{settings.OTP_MAX_VERIFY_ATTEMPTS}")

        if attempts >= settings.OTP_MAX_VERIFY_ATTEMPTS:
            # Trigger Lockout: Destroy OTP and lock account verification
            pipe = redis_client.pipeline()
            pipe.delete(keys["code"], keys["attempts"])
            pipe.set(keys["lockout"], "1", ex=settings.OTP_LOCKOUT_SECONDS)
            pipe.execute()

            logger.error(f"User {email} reached max OTP verify attempts ({attempts}). Locked for {settings.OTP_LOCKOUT_SECONDS}s.")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many incorrect attempts. Verification is locked for {settings.OTP_LOCKOUT_SECONDS // 60} minutes."
            )

        remaining = settings.OTP_MAX_VERIFY_ATTEMPTS - attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OTP code. {remaining} attempt(s) remaining before temporary lockout."
        )
