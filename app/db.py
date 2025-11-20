# app/db.py
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
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
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    """Initialize database - migration approach now handles table creation."""
    # Note: With Alembic migrations, table creation is handled by:
    # 1. Alembic migrations on startup (via start.py run_migrations())
    # 2. For tests/dev: pytest conftest.py handles migrations
    # Avoid using create_all() here as it conflicts with migration tracking
    logger.debug("Database initialized (migrations manage schema).")
