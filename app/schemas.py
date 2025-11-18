from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from .i18n import gettext as _


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
