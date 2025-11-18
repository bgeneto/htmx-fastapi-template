# app/db.py
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import settings
from .logger import get_logger

logger = get_logger("db")

# settings.database_url should come from pydantic BaseSettings reading .env
DATABASE_URL = settings.DATABASE_URL

# create async engine for the app
engine: AsyncEngine = create_async_engine(
    DATABASE_URL, echo=settings.debug, pool_pre_ping=True
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    # dev convenience - create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.debug("Database initialized (create_all used for dev).")
