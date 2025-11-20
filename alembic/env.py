# alembic/env.py
import logging
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ensure project root on path so `app` imports work
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# import your models so metadata is populated
from app.models import *  # noqa: F401

config = context.config
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

from sqlmodel import SQLModel

# The metadata for autogenerate:
target_metadata = SQLModel.metadata


def _make_sync_url(async_url: str) -> str:
    """
    Convert an async DB URL to a sync URL usable by Alembic.
    Examples:
      - sqlite+aiosqlite:///./dev.db -> sqlite:///./dev.db
      - postgresql+asyncpg://user:pwd@host/db -> postgresql://user:pwd@host/db
      - mysql+aiomysql:// -> mysql://  (or mysql+pymysql recommended for sync)
    """
    if async_url is None:
        return async_url
    # common async dialect markers
    markers = ["+asyncpg", "+aiomysql", "+asyncmy", "+aiosqlite"]
    for m in markers:
        if m in async_url:
            return async_url.replace(m, "")
    return async_url


def get_database_url() -> str:
    # 1) Try to load from Pydantic settings (respects .env file)
    try:
        from app.config import settings

        return settings.DATABASE_URL
    except (ImportError, ValueError):
        pass
    # 2) environment variable
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    # 3) fallback to alembic.ini sqlalchemy.url
    url = config.get_main_option("sqlalchemy.url")
    return url


def run_migrations_offline():
    url = get_database_url()
    sync_url = _make_sync_url(url)
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # alembic expects a sync driver; ensure config has the sync url
    url = get_database_url()
    sync_url = _make_sync_url(url)
    config.set_main_option("sqlalchemy.url", sync_url)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
