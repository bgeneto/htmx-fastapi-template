"""
Custom SQLModel User Database adapter for fastapi-users

This adapter fixes the async/await issues in the fastapi-users-db-sqlmodel package.
"""
from typing import Generic, Optional, Type

from fastapi_users.db import BaseUserDatabase
from fastapi_users.models import UP
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


class SQLModelUserDatabase(Generic[UP], BaseUserDatabase[UP, int]):
    """
    Database adapter for SQLModel working with fastapi-users.
    
    Properly handles async operations with SQLModel's AsyncSession.
    """

    def __init__(self, session: AsyncSession, user_model: Type[UP]):
        self.session = session
        self.user_model = user_model

    async def get(self, id: int) -> Optional[UP]:
        """Get a user by ID"""
        result = await self.session.execute(
            select(self.user_model).where(self.user_model.id == id)  # type: ignore
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[UP]:
        """Get a user by email"""
        result = await self.session.execute(
            select(self.user_model).where(self.user_model.email == email)  # type: ignore
        )
        return result.scalar_one_or_none()

    async def create(self, create_dict: dict) -> UP:
        """Create a new user"""
        user = self.user_model(**create_dict)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user: UP, update_dict: dict) -> UP:
        """Update a user"""
        for key, value in update_dict.items():
            setattr(user, key, value)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user: UP) -> None:
        """Delete a user"""
        await self.session.delete(user)
        await self.session.commit()
