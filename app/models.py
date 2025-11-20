from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    """User role hierarchy: pending < user < moderator < admin"""

    PENDING = "pending"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class User(SQLModel, table=True):
    """User model for authentication and authorization"""

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    full_name: str = Field(max_length=200)

    # Password is optional - only used for bootstrap admin
    # All other users use magic link authentication
    hashed_password: Optional[str] = Field(default=None, max_length=255)

    role: UserRole = Field(default=UserRole.PENDING)
    is_active: bool = Field(default=True)
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

    created_at: datetime = Field(default_factory=datetime.utcnow)


class Contact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=200)
    email: str = Field(index=True, max_length=320)
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
