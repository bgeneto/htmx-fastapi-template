# FastAPI + Alpine.js Starter

A professional, enterprise-grade starter template featuring FastAPI, Alpine.js, and Tailwind CSS with full internationalization (i18n) support.

**Features:**
- FastAPI with async/await and dependency injection
- Alpine.js for reactive client-side components
- Axios for clean, consistent AJAX calls (replaces fetch)
- HTMX for seamless server-driven HTML updates (prefer Alpine.js + Axios though)
- **Internationalization (i18n)** - Multi-language support with Babel
- Pydantic v2 for validation (server-side + client-side)
- SQLModel (async SQLAlchemy) for DB models and persistence
- Async DB session management with repository pattern
- Structured logging with Loguru
- Environment config via Pydantic BaseSettings
- Database migrations with Alembic
- Tailwind CSS 4.x (PostCSS) for modern styling
- Professional folder structure (templates, static organization)
- Full authentication system with magic link login
- Role-based access control (PENDING, USER, MODERATOR, ADMIN)

## 📁 Project Structure

```
fastapi-alpine-starter/
├── app/                              # Application core
│   ├── main.py                       # FastAPI app & route handlers
│   ├── config.py                     # Configuration (Pydantic BaseSettings)
│   ├── models.py                     # SQLModel table definitions
│   ├── schemas.py                    # Pydantic validation schemas
│   ├── repository.py                 # Data access layer (CRUD)
│   ├── auth.py                       # Session & authentication
│   ├── email.py                      # Email service (Resend)
│   ├── i18n.py                       # i18n utilities
│   ├── logger.py                     # Logging configuration
│   ├── db.py                         # Database engine & sessions
│   └── create_db.py                  # Database initialization
│
├── templates/                        # Jinja2 templates
│   ├── _base.html                    # Root template (layout, head, footer)
│   ├── components/                   # Reusable components
│   │   ├── _theme_toggle.html        # Dark/light mode toggle
│   │   ├── _language_selector.html   # Language selection
│   │   ├── _form_alpine.html         # Form component with Alpine.js
│   │   └── _recent_contacts.html     # Recent contacts partial
│   └── pages/                        # Full-page templates
│       ├── index.html                # Homepage
│       ├── auth/                     # Authentication pages
│       │   ├── login.html            # Magic link login
│       │   ├── register.html         # User registration
│       │   └── check_email.html      # Email verification
│       └── admin/                    # Admin pages
│           ├── login.html            # Admin password login
│           ├── index.html            # Admin dashboard
│           └── users.html            # User management
│
├── static/                           # Static assets
│   ├── css/                          # Stylesheets
│   │   ├── input.css                 # Tailwind source
│   │   └── output.css                # Compiled CSS (generated)
│   ├── icons/                        # SVG icons (Heroicons)
│   ├── images/                       # Image assets
│   └── style.css                     # Custom styles
│
├── alembic/                          # Database migrations
│   ├── env.py                        # Migration configuration
│   └── versions/                     # Migration files
│
├── translations/                     # i18n translation files
│   └── pt_BR/                        # Portuguese (Brazil)
│       └── LC_MESSAGES/
│           ├── messages.po           # Translation strings
│           └── messages.mo           # Compiled translations
│
├── docs/                             # Documentation
│   ├── ARCHITECTURE.md               # Folder structure & design rationale
│   ├── AUTHENTICATION.md             # Auth system details
│   ├── MIGRATIONS.md                 # Database migrations guide
│   ├── TAILWIND_SETUP.md             # CSS build process
│   └── I18N.md                       # i18n implementation guide
│
├── tests/                            # Test suite
│   ├── conftest.py                   # Pytest fixtures
│   └── test_contact.py               # Contact form tests
│
├── scripts/                          # Utility scripts
│   └── pre-commit.sh                 # Git pre-commit hook
│
├── Configuration files
│   ├── pyproject.toml                # Python project metadata
│   ├── requirements.txt               # Python dependencies
│   ├── package.json                  # Node.js dependencies
│   ├── postcss.config.js             # PostCSS configuration
│   ├── babel.cfg                     # Babel i18n config
│   ├── alembic.ini                   # Alembic configuration
│   ├── .env.example                  # Environment variable template
│   └── .gitignore                    # Git ignore rules
│
├── Docker files
│   ├── Dockerfile                    # Multi-stage Docker build
│   └── compose.yml                   # Docker Compose config
│
├── Scripts
│   ├── start.py                      # Application startup
│   ├── setup-tailwind.sh             # Tailwind CSS setup
│   ├── translate.sh                  # i18n management
│   └── main.py                       # Entry point
│
└── Documentation
    ├── README.md                     # This file
    ├── RESTRUCTURING_SUMMARY.md      # Restructuring changes
    └── .github/
        ├── copilot-instructions.md   # Development guidelines
        └── workflows/
            └── ci.yml                # CI/CD pipeline
```

### Key Directories Explained

- **app/** - All Python application code (routes, models, business logic)
- **templates/** - Jinja2 HTML templates, organized by feature (pages, components)
- **static/css/** - Tailwind CSS files (input source, compiled output)
- **docs/** - Comprehensive documentation for development and deployment
- **alembic/** - Database schema evolution and migrations
- **translations/** - Multi-language support files (auto-generated during build)

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

**📖 Full documentation:** See [docs/I18N.md](docs/I18N.md) for complete i18n guide

## 🚀 Run locally (development)

```bash
# 1. Python setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Build Tailwind CSS (required)
npm install
npm run build:css

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings (DATABASE_URL, SECRET_KEY, DEBUG, LOG_FILE)
python -m app.create_db  # create tables for dev

# 4. Compile translations (required for i18n)
./translate.sh compile

# 5. Run the app
uvicorn app.main:app --reload
```

**For active development**, run Tailwind in watch mode in a separate terminal:
```bash
npm run watch:css  # Auto-rebuilds CSS on template changes
```

## 🐳 Docker / Docker Compose

**Quick start with Docker Compose:**
```bash
docker-compose up --build
```

The Dockerfile automatically:
- Installs Node.js and npm dependencies
- Builds Tailwind CSS (creates `static/output.css`)
- Compiles translations
- Runs the FastAPI application

**Production Docker build:**
```bash
docker build -t fastapi-alpine-starter .
docker run -p 8000:8000 fastapi-alpine-starter
```

.env example:
```
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/fastapi_alpine
SECRET_KEY=change-me
ENV=development
DEBUG=true
LOG_FILE=logs/app.log
```

Notes:
- For production, run Alembic migrations instead of create_db.
- Set `DEBUG=true` in `.env` to enable DEBUG-level logging
- Set `LOG_FILE=logs/app.log` to enable file logging (optional, defaults to console-only)
- Log files auto-rotate at 10MB, kept for 7 days, and compressed as zip
- The scaffold focuses on patterns and a clean separation of concerns.

Notes:
- **Logging**: Set `DEBUG=true` to enable debug logs. Set `LOG_FILE` to enable file logging (rotated at 10MB, kept for 7 days).
- For production, run Alembic migrations instead of create_db.
- The scaffold focuses on patterns and a clean separation of concerns.
