from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


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
