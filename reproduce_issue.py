
import asyncio
from typing import List, Optional
from sqlmodel import Field, SQLModel, create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.grid_engine import GridEngine, PaginatedResponse
from fastapi import Request

# Mock Request
class MockRequest:
    def __init__(self, query_params):
        self.query_params = query_params

# Define Model (same as app/models.py but simplified for standalone run if needed, 
# but better to import if possible. Since I can't easily import due to relative imports in app, 
# I will redefine Car here matching the structure)

class Car(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    make: str = Field(index=True, max_length=100)
    model: str = Field(index=True, max_length=100)
    version: str = Field(max_length=100)
    year: int = Field(index=True)
    price: float

async def reproduce():
    # Setup DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Seed data
        car = Car(make="Toyota", model="Camry", version="XLE", year=2024, price=25000.0)
        session.add(car)
        await session.commit()

        grid = GridEngine(session, Car)
        search_fields = ["make", "model", "version", "year", "price"]

        print("--- Test 1: Search '20' (Numeric Partial Match) ---")
        # Expectation: Should find 2024.
        # Current behavior prediction: Will fail because int("20") != 2024
        req = MockRequest({"q": "20"})
        result = await grid.get_page(req, search_fields=search_fields)
        print(f"Search '20' found: {result.total} items")
        if result.total == 0:
            print("FAIL: Did not find 2024 with query '20'")
        else:
            print("PASS: Found 2024 with query '20'")

        print("\n--- Test 2: Search 'oyota' (Starts-with vs Contains) ---")
        # Expectation: Should NOT find Toyota (starts-with).
        # Current behavior prediction: Will find it because it uses %query%
        req = MockRequest({"q": "oyota"})
        result = await grid.get_page(req, search_fields=search_fields)
        print(f"Search 'oyota' found: {result.total} items")
        if result.total > 0:
            print("FAIL: Found Toyota with query 'oyota' (Contains match instead of Starts-with)")
        else:
            print("PASS: Did not find Toyota with query 'oyota'")

        print("\n--- Test 3: Search 'Toy' (Starts-with) ---")
        # Expectation: Should find Toyota.
        req = MockRequest({"q": "Toy"})
        result = await grid.get_page(req, search_fields=search_fields)
        print(f"Search 'Toy' found: {result.total} items")
        
        print("\n--- Test 4: Search 'Toy' AND Filter Year=2024 ---")
        # Expectation: Should find Toyota.
        req = MockRequest({"q": "Toy", "year": "2024"})
        result = await grid.get_page(req, search_fields=search_fields)
        print(f"Search 'Toy' + Year=2024 found: {result.total} items")

if __name__ == "__main__":
    asyncio.run(reproduce())
