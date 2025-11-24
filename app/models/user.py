from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import field_validator
from sqlalchemy.types import Text
from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    """User role hierarchy: pending < user < moderator < admin"""

    PENDING = "pending"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class User(SQLModel, table=True):
    """User model for authentication and authorization

    Compatible with fastapi-users while maintaining custom role-based access control.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    full_name: str = Field(max_length=200)
    phone: Optional[str] = Field(default=None, max_length=20)

    # Profile picture stored as data URL (base64)
    profile_picture: Optional[str] = Field(default=None, sa_type=Text)

    # Required by fastapi-users - empty string for magic link users
    hashed_password: str = Field(default="", max_length=255)

    # Custom role-based access control
    role: UserRole = Field(default=UserRole.PENDING)

    # fastapi-users standard fields
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)  # Maps to ADMIN role
    is_verified: bool = Field(default=False)  # Maps to email_verified

    # Deprecated field kept for backward compatibility
    email_verified: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserBase(SQLModel):
    """Base User model class is required for proper validation (table=False, validates like Pydantic)"""

    email: str = Field(description="Email address", max_length=320)
    full_name: str = Field(max_length=200)
    role: UserRole = Field(default=UserRole.USER)
    is_active: bool = Field(default=True)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """Custom full_name validation with translated error message"""
        if not v or len(v.strip()) < 2:
            from ..i18n import gettext as _

            raise ValueError(_("Name must be at least 2 characters"))
        return v.strip()

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Custom email validation with translated error message"""
        if not v or "@" not in v or "." not in v.split("@")[-1]:
            from ..i18n import gettext as _

            raise ValueError(_("Please enter a valid email address"))
        return v.strip().lower()
