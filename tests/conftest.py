import os

import pytest
from httpx import AsyncClient
from sqlmodel import SQLModel


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
    from app.db import engine
    from app.main import app

    # For tests: create all tables directly since we use a temp database
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
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
