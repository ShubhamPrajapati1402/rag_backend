import pytest
from unittest.mock import patch
import fakeredis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.document import Base
from app.models.user import User
from app.db.session import get_db
from app.main import app
from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token
from app.services.otp_service import OTPService
from app.core.config import settings

# In-memory SQLite database for isolated unit & API testing
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(autouse=True)
def setup_db_and_redis():
    """
    Sets up a clean in-memory database and fakeredis client for every test.
    """
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    
    # Fake Redis instance
    fake_redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
    
    def override_get_db():
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    
    with patch("app.core.redis_client.get_redis_client", return_value=fake_redis_client), \
         patch("app.services.otp_service.get_redis_client", return_value=fake_redis_client):
        yield db, fake_redis_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)

def test_password_hashing():
    pwd = "MySecretPassword123!"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_jwt_token_flow():
    token = create_access_token(subject=42, claims={"email": "test@example.com"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["email"] == "test@example.com"

def test_otp_rate_limiting_and_lockout(setup_db_and_redis):
    _, fake_redis = setup_db_and_redis
    email = "ratelimit@example.com"

    # 1. Store initial OTP
    otp_code = OTPService.generate_otp_code()
    assert len(otp_code) == settings.OTP_LENGTH
    OTPService.store_otp(email, otp_code, purpose="signup")

    # 2. Resend Cooldown should trigger 429
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        OTPService.check_request_rate_limit(email, purpose="signup")
    assert exc_info.value.status_code == 429
    assert "cooldown" in exc_info.value.detail.lower() or "wait" in exc_info.value.detail.lower()

    # Clear cooldown to test failed attempts
    fake_redis.delete(f"otp:cooldown:signup:{email}")

    # 3. Wrong OTP entries should increment failed attempts
    for i in range(1, settings.OTP_MAX_VERIFY_ATTEMPTS):
        with pytest.raises(HTTPException) as exc:
            OTPService.verify_otp(email, "000000", purpose="signup")
        assert exc.value.status_code == 400
        assert "remaining" in exc.value.detail.lower()

    # 4. Exceeding max attempts triggers Lockout
    with pytest.raises(HTTPException) as exc:
        OTPService.verify_otp(email, "000000", purpose="signup")
    assert exc.value.status_code == 429
    assert "locked" in exc.value.detail.lower()

def test_full_auth_api_flow(setup_db_and_redis):
    _, fake_redis = setup_db_and_redis
    client = TestClient(app)

    # 1. Signup Request
    signup_payload = {
        "email": "alex.doe@example.com",
        "password": "SecurePassword123!",
        "full_name": "Alex Doe"
    }
    signup_res = client.post("/api/v1/auth/signup", json=signup_payload)
    assert signup_res.status_code == 201
    assert "verification code" in signup_res.json()["message"]

    # Retrieve generated OTP from Redis
    stored_otp = fake_redis.get(f"otp:code:signup:{signup_payload['email']}")
    assert stored_otp is not None

    # 2. Login Before Verification -> should be blocked with 403
    login_payload = {
        "email": "alex.doe@example.com",
        "password": "SecurePassword123!"
    }
    login_unverified_res = client.post("/api/v1/auth/login", json=login_payload)
    assert login_unverified_res.status_code == 403
    assert "not verified" in login_unverified_res.json()["detail"]

    # 3. Verify OTP
    verify_payload = {
        "email": "alex.doe@example.com",
        "otp_code": stored_otp
    }
    verify_res = client.post("/api/v1/auth/verify-otp", json=verify_payload)
    assert verify_res.status_code == 200
    assert verify_res.json()["user"]["is_verified"] is True
    assert settings.COOKIE_NAME in verify_res.cookies

    # 4. Access Protected Route /me with Session Cookie
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "alex.doe@example.com"
    assert me_res.json()["full_name"] == "Alex Doe"

    # 5. Access /me without Cookie -> should fail with 401
    unauth_client = TestClient(app)
    unauth_me_res = unauth_client.get("/api/v1/auth/me")
    assert unauth_me_res.status_code == 401

    # 6. Logout on authenticated client
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200
    assert "Logged out" in logout_res.json()["message"]

    # 7. Access /me after Logout -> should fail with 401
    after_logout_me = client.get("/api/v1/auth/me")
    assert after_logout_me.status_code == 401

def test_google_auth_flow(setup_db_and_redis):
    client = TestClient(app)
    fake_google_payload = {
        "email": "googleuser@example.com",
        "name": "Google User",
        "picture": "https://lh3.googleusercontent.com/a/photo.jpg",
        "sub": "google-123456789"
    }

    with patch("app.services.google_auth_service.GoogleAuthService.verify_token", return_value=fake_google_payload):
        res = client.post("/api/v1/auth/google", json={"id_token": "fake_id_token"})
        assert res.status_code == 200
        assert res.json()["user"]["email"] == "googleuser@example.com"
        assert res.json()["user"]["auth_provider"] == "google"
        assert res.json()["user"]["is_verified"] is True
        assert settings.COOKIE_NAME in res.cookies

        # Verify access to /me
        me_res = client.get("/api/v1/auth/me")
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "googleuser@example.com"
        assert me_res.json()["auth_provider"] == "google"

def test_resend_otp_flow(setup_db_and_redis):
    _, fake_redis = setup_db_and_redis
    client = TestClient(app)

    # 1. Signup unverified user
    client.post("/api/v1/auth/signup", json={
        "email": "resend.test@example.com",
        "password": "Password123!",
        "full_name": "Resend Tester"
    })
    initial_otp = fake_redis.get("otp:code:signup:resend.test@example.com")
    assert initial_otp is not None

    # Clear cooldown to simulate waiting period
    fake_redis.delete("otp:cooldown:signup:resend.test@example.com")

    # 2. Resend OTP
    res = client.post("/api/v1/auth/resend-otp", json={"email": "resend.test@example.com"})
    assert res.status_code == 200
    assert "fresh verification code" in res.json()["message"]

    new_otp = fake_redis.get("otp:code:signup:resend.test@example.com")
    assert new_otp is not None
