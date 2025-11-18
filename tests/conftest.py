import os
import asyncio
import tempfile
import pytest
from sqlmodel import SQLModel
from sqlmodel import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from httpx import AsyncClient

# ensure test DB in temp file to support SQLite autogenerate
@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory):
    p = tmp_path_factory.mktemp("data") / "test.db"
    return str(p)

@pytest.fixture(scope="session")
def database_url(tmp_db_path):
    return f"sqlite+aiosqlite:///{tmp_db_path}"

@pytest.fixture(scope="session")
async def initialized_app(database_url):
    # set env var before importing app modules that read settings
    os.environ["DATABASE_URL"] = database_url
    from app.main import app
    from app.db import engine
    # create tables
    from app.db import init_db
    await init_db()
    yield app
    # teardown: dispose engine
    try:
        await engine.dispose()
    except Exception:
        pass

@pytest.fixture
async def client(initialized_app):
    from app.main import app
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac
