from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel
from sqlalchemy.types import Text


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
    year: int = Field(index=True, gt=1886, description="Year must be after 1886")
    price: float = Field(gt=0, description="Price must be greater than 0")


class Car(CarBase, table=True):
    """Car table model - inherits validation from CarBase"""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BookBase(SQLModel):
    """Base Book model class is required for proper validation (table=False, validates like Pydantic)"""

    title: str = Field(index=True, max_length=200, min_length=1)
    author: str = Field(index=True, max_length=200, min_length=1)
    year: int = Field(index=True, ge=1, description="Year must be at least 1")
    pages: int = Field(ge=1, description="Pages must be at least 1")
    summary: str = Field(sa_type=Text, min_length=1)


class Book(BookBase, table=True):
    """Book table model - inherits validation from BookBase"""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
