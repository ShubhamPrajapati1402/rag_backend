from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator

class UserSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    full_name: Optional[str] = Field(None, max_length=255)

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleAuthRequest(BaseModel):
    id_token: str = Field(..., description="Google OAuth2 ID Token returned by Google Identity Services")

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(..., description="OTP code received via email")

    @model_validator(mode="before")
    @classmethod
    def normalize_otp_field(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Accept 'otp', 'code', or 'otp_code' from the frontend
            code = values.get("otp_code") or values.get("otp") or values.get("code")
            if code is not None:
                values["otp_code"] = str(code).strip()
        return values

class OTPResendRequest(BaseModel):
    email: EmailStr

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    auth_provider: str
    is_verified: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AuthMessageResponse(BaseModel):
    message: str
    user: Optional[UserResponse] = None
    email: Optional[str] = None

class TokenResponse(BaseModel):
    message: str
    user: UserResponse
    access_token: Optional[str] = None
    token_type: Optional[str] = "bearer"
