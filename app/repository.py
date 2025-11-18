from typing import AsyncGenerator, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from .models import Contact
from .schemas import ContactCreate
from .db import AsyncSessionLocal
from .logger import get_logger

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
    result = await session.execute(__import__("sqlmodel").sql.select(Contact).limit(limit))
    return result.scalars().all()
