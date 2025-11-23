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


class LoginToken(SQLModel, table=True):
    """Magic link login tokens"""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    # Store hashed token for security
    token_hash: str = Field(index=True, max_length=64)

    expires_at: datetime = Field(index=True)
    used_at: Optional[datetime] = Field(default=None)
    usage_count: int = Field(default=0)  # Track how many times the link has been used

    created_at: datetime = Field(default_factory=datetime.utcnow)


class OTPCode(SQLModel, table=True):
    """OTP verification codes for login"""

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, max_length=320)
    code: str = Field(max_length=6)  # 6-digit code

    expires_at: datetime = Field(index=True)
    used_at: Optional[datetime] = Field(default=None)
    attempts: int = Field(default=0)  # Track failed attempts

    created_at: datetime = Field(default_factory=datetime.utcnow)


class Contact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=200)
    email: str = Field(index=True, max_length=320)
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CarBase(SQLModel):
    """Base Car model class is required for proper validation (table=False, validates like Pydantic)"""

    make: str = Field(index=True, max_length=100, min_length=1)
    model: str = Field(index=True, max_length=100, min_length=1)
    version: str = Field(max_length=100, min_length=1)
    year: int = Field(index=True)
    price: float

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        if v <= 1886:
            from .i18n import gettext as _
            raise ValueError(_("Year must be after 1886"))
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v <= 0:
            from .i18n import gettext as _
            raise ValueError(_("Price must be greater than 0"))
        return v


class Car(CarBase, table=True):
    """Car table model - inherits validation from CarBase"""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BookBase(SQLModel):
    """Base Book model class is required for proper validation (table=False, validates like Pydantic)"""

    title: str = Field(index=True, max_length=200, min_length=1)
    author: str = Field(index=True, max_length=200, min_length=1)
    year: int = Field(index=True)
    pages: int
    summary: str = Field(sa_type=Text, min_length=1)

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        if v <= 1450:
            from .i18n import gettext as _
            raise ValueError(_("Year must be after 1450"))
        return v

    @field_validator("pages")
    @classmethod
    def validate_pages(cls, v: int) -> int:
        if v < 1:
            from .i18n import gettext as _
            raise ValueError(_("Pages must be at least 1"))
        return v


class Book(BookBase, table=True):
    """Book table model - inherits validation from BookBase"""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
            from .i18n import gettext as _
            raise ValueError(_("Name must be at least 2 characters"))
        return v.strip()

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Custom email validation with translated error message"""
        if not v or "@" not in v or "." not in v.split("@")[-1]:
            from .i18n import gettext as _
            raise ValueError(_("Please enter a valid email address"))
        return v.strip().lower()
