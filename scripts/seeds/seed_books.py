#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from faker import Faker
from sqlmodel import SQLModel

from app.db import AsyncSessionLocal, engine
from app.logger import get_logger
from app.models import Book

logger = get_logger("seed_books")
fake = Faker()

async def seed_books(count: int = 100):
    # Create tables if they don't exist (for testing purposes)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSessionLocal() as session:
        logger.info(f"Seeding {count} books...")

        for _ in range(count):
            book = Book(
                title=fake.catch_phrase(),
                author=fake.name(),
                year=int(fake.year()),
                pages=fake.random_int(min=100, max=1000),
                summary=fake.text(max_nb_chars=500)
            )
            session.add(book)

        await session.commit()
        logger.info("Books seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_books())
