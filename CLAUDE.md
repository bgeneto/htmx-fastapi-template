# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a professional FastAPI + Alpine.js starter template with full internationalization support. It combines server-side rendering with client-side reactivity using modern async patterns.

**Tech Stack:**
- Backend: FastAPI (async), SQLModel (async SQLAlchemy), Pydantic v2
- Frontend: Alpine.js, HTMX, Tailwind CSS v4, Axios
- Database: Async PostgreSQL (prod) or SQLite (dev)
- Auth: Magic link login with role-based access control
- i18n: Full internationalization with Babel (English + Portuguese)

## Essential Development Commands

### Initial Setup (Required)
```bash
# Python environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# CSS build (REQUIRED before first run - styling breaks without this)
npm install && npm run build:css

# Translations (REQUIRED for i18n to work)
./translate.sh compile

# Database setup (development only)
python -m app.create_db

# Run development server
uvicorn app.main:app --reload
```

### Active Development Workflow
```bash
npm run watch:css           # Auto-rebuild CSS on changes (run in separate terminal)
./translate.sh refresh      # Update translations after code changes
pytest                      # Run tests
alembic revision --autogenerate -m "Message"  # Create DB migrations
```

### Docker Development
```bash
docker-compose up --build   # Full development environment
```

## Critical Architecture Patterns

### 1. Repository Pattern with Async Sessions
- All database operations go through `app/repository.py`
- Uses dependency injection with `get_session()`
- Async session management throughout - never use sync sessions

### 2. Strategy Pattern Implementation
- `app/strategies.py` contains validation and auth strategies
- Reduces endpoint complexity via polymorphism
- Centralized error handling and i18n

### 3. Dual Validation (Client + Server)
- Server-side: Pydantic schemas in `app/schemas.py`
- Client-side: Alpine.js validation mirrors server rules
- Maintain consistency between frontend/backend validation

### 4. Data Grid System
- Advanced data grid with search, filtering, sorting in `app/grid_engine.py`
- Partial matching capabilities for search
- Admin interface for data management

## Key Development Rules

### **CRITICAL REQUIREMENTS**
1. **Must run `npm run build:css`** before first run - styling breaks without compiled CSS
2. **Must run `./translate.sh compile`** for i18n to work
3. **Never edit `static/css/output.css`** - it's auto-generated from `input.css`
4. **Always use Axios for AJAX** - never fetch() in templates
5. **Wrap ALL user-facing text in `_()`** for i18n support
6. **Use async/await consistently** - this is an async-first codebase

### **Common Pitfalls to Avoid**
- Missing `output.css` causes complete styling break
- Untranslated strings break i18n experience
- Session lifecycle issues with manual session management
- Alpine.js state initialization problems
- Using sync database operations instead of async

## Important File Locations

### Core Application Files
- `app/main.py` - FastAPI app & all routes (large file, well-organized)
- `app/models.py` - SQLModel table definitions
- `app/schemas.py` - Pydantic validation schemas
- `app/repository.py` - Data access layer (CRUD operations)
- `app/strategies.py` - Strategy patterns for validation/auth
- `app/grid_engine.py` - Data grid functionality

### Frontend Structure
- `templates/_base.html` - Root template with Alpine.js setup
- `templates/components/` - Reusable components
- `templates/pages/` - Full-page templates by feature
- `static/css/input.css` - Tailwind source (EDIT THIS)
- `static/css/output.css` - Compiled CSS (AUTO-GENERATED)

### Configuration & Environment
- `app/config.py` - Pydantic BaseSettings for environment variables
- `.env` - Environment configuration (copy from `.env.example`)
- Key variables: `DATABASE_URL`, `SECRET_KEY`, `ENV`, `DEBUG`, `LOG_FILE`

## Testing Framework
- **pytest + pytest-asyncio** for async testing
- **httpx AsyncClient** for FastAPI testing
- Test database setup in `conftest.py`
- Limited test coverage currently (only `test_contact.py`)

## Internationalization Workflow
- Template strings: `{{ _('Text') }}`
- Python code: Import and use `_()` function
- Automatic locale detection + manual language selector
- Translation workflow managed via `translate.sh` script
- Supported languages: English (default), Portuguese (pt_BR)

## Database & Migrations
- Development: `python -m app.create_db` (creates tables)
- Production: Use Alembic migrations
- Async database operations only
- Repository pattern abstracts database access

## Current Development Status
- **Current branch**: `alpine-datagrid`
- **Active features**: Data grid enhancements, Car model, Portuguese translations
- **Architecture**: Production-ready with enterprise-grade patterns
- **Documentation**: Comprehensive docs in `docs/` folder

This is a well-architected starter template demonstrating clean separation of concerns, proper async/await usage, and FastAPI best practices throughout.