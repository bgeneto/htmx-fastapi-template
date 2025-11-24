from datetime import datetime
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, SQLModel


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
            from ..i18n import gettext as _

            raise ValueError(_("Year must be after 1886"))
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v <= 0:
            from ..i18n import gettext as _

            raise ValueError(_("Price must be greater than 0"))
        return v


class Car(CarBase, table=True):
    """Car table model - inherits validation from CarBase"""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
