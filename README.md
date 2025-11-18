# FastAPI + HTMX Enterprise Starter

Features:
- FastAPI app with HTMX progressive enhancement patterns
- **Internationalization (i18n)** - Multi-language support with Babel
- Pydantic v2 for validation (server-side)
- SQLModel (SQLAlchemy) for DB models and persistence
- Async DB session management and simple repository pattern
- Structured logging with Loguru + logging adapter
- Environment config via pydantic BaseSettings
- Development helper script to create the DB schema
- Simple migration hint using Alembic (template included)

## 🌍 Internationalization

This project includes full i18n support with **automatic detection** and **manual language selector**:

- **Supported Languages**: English (default), Portuguese (pt_BR)
- **Language Selector UI**: Globe icon in header - click to change language
- **Auto-detection**: From browser Accept-Language header (works on first visit)
- **Persistent**: Language choice saved in cookie
- **Coverage**: All UI strings, validation messages, and dynamic content

**Quick Start:**
```bash
# Add a new language
./translate.sh init es

# Update translations after code changes
./translate.sh refresh
```

**Users can switch language:**
- Click the 🌐 globe icon in the top-right corner
- Or it auto-detects from browser language on first visit

**📖 Full documentation:** See [I18N.md](I18N.md) for complete i18n guide

## 🚀 Run locally (development)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# configure DATABASE_URL in .env (example below)
python -m app.create_db  # create tables for dev

# Compile translations (required for i18n)
./translate.sh compile

# Start the server
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
