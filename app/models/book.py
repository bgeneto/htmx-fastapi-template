from datetime import datetime
from typing import Optional

from pydantic import field_validator
from sqlalchemy.types import Text
from sqlmodel import Field, SQLModel


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
            from ..i18n import gettext as _

            raise ValueError(_("Year must be after 1450"))
        return v

    @field_validator("pages")
    @classmethod
    def validate_pages(cls, v: int) -> int:
        if v < 1:
            from ..i18n import gettext as _

            raise ValueError(_("Pages must be at least 1"))
        return v


class Book(BookBase, table=True):
    """Book table model - inherits validation from BookBase"""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
