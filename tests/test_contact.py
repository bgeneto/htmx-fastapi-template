import pytest
from httpx import AsyncClient
from sqlmodel import select
from app.models import Contact
from app.db import AsyncSessionLocal

@pytest.mark.asyncio
async def test_post_contact(client: AsyncClient):
    # post a valid contact via the form endpoint
    data = {'name': 'Alice', 'email': 'alice@example.com', 'message': 'Hello world'}
    resp = await client.post("/contact", data=data, headers={"Accept":"text/html"})
    assert resp.status_code in (200, 303)
    # verify DB has the contact
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Contact).where(Contact.email == 'alice@example.com'))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].name == 'Alice'
