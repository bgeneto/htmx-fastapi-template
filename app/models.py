from typing import Optional
from sqlmodel import SQLModel, Field, SQLModel
from datetime import datetime

class Contact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=200)
    email: str = Field(index=True, max_length=320)
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
