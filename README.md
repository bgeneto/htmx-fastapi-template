# FastAPI + HTMX Enterprise Starter

Features:
- FastAPI app with HTMX progressive enhancement patterns
- Pydantic v2 for validation (server-side)
- SQLModel (SQLAlchemy) for DB models and persistence
- Async DB session management and simple repository pattern
- Structured logging with Loguru + logging adapter
- Environment config via pydantic BaseSettings
- Development helper script to create the DB schema
- Simple migration hint using Alembic (template included)

Run locally (development):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# configure DATABASE_URL in .env (example below)
python -m app.create_db  # create tables for dev
uvicorn app.main:app --reload
```

.env example:
```
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/fastapi_htmx
SECRET_KEY=change-me
ENV=development
```

Notes:
- For production, run Alembic migrations instead of create_db.
- The scaffold focuses on patterns and a clean separation of concerns.
