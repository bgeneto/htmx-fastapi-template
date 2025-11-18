from pydantic import BaseModel, Field, EmailStr, constr
from typing import Optional
from datetime import datetime

class ContactCreate(BaseModel):
    name: constr(min_length=2, strict=True) = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    message: constr(min_length=5) = Field(..., description="Message text")

class ContactRead(BaseModel):
    id: int
    name: str
    email: EmailStr
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
