from typing import AsyncGenerator

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .db import AsyncSessionLocal
from .logger import get_logger
from .models import Contact
from .schemas import ContactCreate

logger = get_logger("repo")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def create_contact(session: AsyncSession, payload: ContactCreate) -> Contact:
    contact = Contact.from_orm(payload)  # SQLModel compatible
    session.add(contact)
    await session.commit()
    await session.refresh(contact)
    logger.debug("Created contact: {}", contact.id)
    return contact


async def list_contacts(session: AsyncSession, limit: int = 100):
    """Get contacts ordered by ID descending"""
    result = await session.execute(
        select(Contact).order_by(Contact.id.desc()).limit(limit)
    )
    return result.scalars().all()


async def get_recent_contacts(session: AsyncSession, limit: int = 4):
    """Get the most recent contacts ordered by creation date"""
    return await list_contacts(session, limit=limit)
