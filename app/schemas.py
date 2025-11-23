from datetime import datetime
from typing import Optional

from fastapi_users import schemas
from pydantic import BaseModel, EmailStr, Field, field_validator

from .i18n import gettext as _
from .models import UserRole

# ============= Contact Schemas =============


class ContactCreate(BaseModel):
    name: str = Field(..., description="Full name", min_length=2)
    email: EmailStr = Field(..., description="Email address")
    message: str = Field(..., description="Message text", min_length=5)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v.strip()) < 2:
            raise ValueError(_("Name must be at least 2 characters"))
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v or len(v.strip()) < 5:
            raise ValueError(_("Message must be at least 5 characters"))
        return v


class ContactRead(BaseModel):
    id: int
    name: str
    email: EmailStr
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ============= FastAPI Users Schemas =============


class UserRead(schemas.BaseUser[int]):
    """Schema for reading user data"""

    full_name: str
    role: UserRole
    email_verified: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(schemas.BaseUserCreate):
    """Schema for creating users"""

    full_name: str = Field(..., description="Full name", min_length=2, max_length=200)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        if not v or len(v.strip()) < 2:
            raise ValueError(_("Name must be at least 2 characters"))
        return v.strip()


class UserUpdate(schemas.BaseUserUpdate):
    """Schema for updating users"""

    full_name: Optional[str] = Field(None, min_length=2, max_length=200)
    role: Optional[UserRole] = None


class UserCreateOTP(BaseModel):
    """Schema for creating users via passwordless OTP login"""

    email: EmailStr = Field(..., description="Email address")
    full_name: str = Field(..., description="Full name", min_length=2, max_length=200)
    is_active: bool = True
    role: UserRole = UserRole.USER

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        if not v or len(v.strip()) < 2:
            raise ValueError(_("Name must be at least 2 characters"))
        return v.strip()


# ============= Legacy Authentication Schemas (kept for compatibility) =============


class UserRegister(BaseModel):
    """Schema for user self-registration (creates pending user)"""

    email: EmailStr = Field(..., description="Email address")
    full_name: str = Field(..., description="Full name", min_length=2, max_length=200)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        if not v or len(v.strip()) < 2:
            raise ValueError(_("Name must be at least 2 characters"))
        return v.strip()


class LoginRequest(BaseModel):
    """Schema for magic link login request"""

    email: EmailStr = Field(..., description="Email address")


class AdminLoginRequest(BaseModel):
    """Schema for admin password login (bootstrap admin only)"""

    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Password", min_length=8)


class AdminCreateUser(BaseModel):
    """Schema for admin-created users with optional password"""

    email: EmailStr = Field(..., description="Email address")
    full_name: str = Field(..., description="Full name", min_length=2, max_length=200)
    role: UserRole = Field(default=UserRole.USER, description="User role")
    password: Optional[str] = Field(None, description="Optional password", min_length=8)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        if not v or len(v.strip()) < 2:
            raise ValueError(_("Name must be at least 2 characters"))
        return v.strip()


class UserResponse(BaseModel):
    """Schema for user response (no sensitive data)"""

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============= Profile Management Schemas =============


class ProfileUpdate(BaseModel):
    """Schema for updating user profile information"""

    full_name: Optional[str] = Field(None, min_length=2, max_length=200)
    email: Optional[EmailStr] = None
    profile_picture: Optional[str] = None  # Data URL for profile picture

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError(_("Name must be at least 2 characters"))
        return v


class PasswordChange(BaseModel):
    """Schema for changing user password"""

    current_password: str = Field(..., description="Current password", min_length=1)
    new_password: str = Field(..., description="New password", min_length=8)
    confirm_password: str = Field(..., description="Confirm new password", min_length=8)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError(_("Passwords do not match"))
        return v
