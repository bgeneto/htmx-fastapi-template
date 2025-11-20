# Project Architecture & Folder Structure

This document explains the professional, enterprise-grade folder structure of the Alpine-FastAPI template project.

## 📁 Project Structure Overview

```
alpine-fastapi/
│
├── app/                              # Main application package
│   ├── __init__.py
│   ├── main.py                       # FastAPI app initialization & route definitions
│   ├── config.py                     # Configuration & environment settings (Pydantic)
│   ├── logger.py                     # Logging setup (Loguru)
│   ├── db.py                         # Database engine & session management
│   ├── create_db.py                  # Database initialization for dev
│   │
│   ├── models.py                     # SQLModel table definitions (User, LoginToken, Contact)
│   ├── repository.py                 # Data access layer (CRUD operations, auth logic)
│   ├── schemas.py                    # Pydantic validation schemas
│   ├── auth.py                       # Authentication & session management
│   ├── email.py                      # Brevo email service integration
│   ├── i18n.py                       # Internationalization utilities
│   │
│   ├── api/                          # API route modules (future expansion)
│   │   ├── __init__.py
│   │   ├── contacts.py               # Contact routes (can be extracted from main.py)
│   │   ├── auth.py                   # Auth routes (can be extracted)
│   │   └── admin.py                  # Admin routes (can be extracted)
│   │
│   ├── core/                         # Core business logic & utilities
│   │   ├── __init__.py
│   │   ├── auth.py                   # Auth dependencies (re-exports from app.auth)
│   │   ├── email.py                  # Email service (re-exports from app.email)
│   │   └── i18n.py                   # i18n utilities (re-exports from app.i18n)
│   │
│   ├── schemas/                      # Organized validation schemas (future expansion)
│   │   ├── __init__.py
│   │   ├── auth.py                   # Auth schemas (re-exports)
│   │   ├── user.py                   # User schemas (re-exports)
│   │   └── contact.py                # Contact schemas (re-exports)
│   │
│   └── middleware/                   # Custom middleware
│       ├── __init__.py
│       └── locale.py                 # Locale/i18n middleware (from app.py)
│
├── templates/                        # Jinja2 template files
│   ├── _base.html                    # Base template (navigation, head, footer)
│   ├── components/                   # Reusable template components
│   │   ├── _theme_toggle.html        # Dark/light mode toggle
│   │   ├── _language_selector.html   # Language selection dropdown
│   │   ├── _form_alpine.html         # Reusable form component with Alpine.js
│   │   └── _recent_contacts.html     # Recent contacts partial
│   ├── pages/                        # Full page templates
│   │   ├── index.html                # Homepage
│   │   ├── auth/                     # Authentication pages
│   │   │   ├── login.html            # Magic link login form
│   │   │   ├── register.html         # User self-registration form
│   │   │   └── check_email.html      # Email verification confirmation
│   │   └── admin/                    # Admin pages
│   │       ├── login.html            # Admin password login
│   │       ├── index.html            # Admin dashboard (contacts)
│   │       └── users.html            # User management page
│   └── layouts/                      # Shared layout templates (future)
│       └── _auth_layout.html         # Auth pages layout template
│
├── static/                           # Static assets
│   ├── css/                          # CSS files
│   │   ├── input.css                 # Tailwind source (with @import directives)
│   │   └── output.css                # Compiled CSS (minified in prod)
│   ├── icons/                        # Icon assets (Heroicons 2.2.0)
│   │   └── heroicons@2.2.0/
│   │       ├── 24/outline/
│   │       └── 24/solid/
│   ├── images/                       # Image assets (future)
│   └── style.css                     # Custom styles
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── conftest.py                   # Pytest fixtures & configuration
│   ├── test_contact.py               # Contact form tests
│   ├── unit/                         # Unit tests
│   ├── integration/                  # Integration tests
│   └── fixtures/                     # Test fixtures & mocks
│
├── alembic/                          # Database migrations
│   ├── env.py                        # Alembic configuration
│   ├── script.py.mako                # Migration template
│   └── versions/                     # Migration files
│       ├── 0001_create_contact_table.py
│       └── 0002_add_auth_tables.py
│
├── scripts/                          # Utility scripts
│   └── pre-commit.sh                 # Pre-commit hook
│
├── docs/                             # Project documentation
│   ├── ARCHITECTURE.md               # This file
│   ├── AUTHENTICATION.md             # Auth system documentation
│   ├── MIGRATIONS.md                 # Database migrations guide
│   ├── TAILWIND_SETUP.md             # CSS build process
│   └── I18N.md                       # Internationalization guide
│
├── translations/                     # i18n translation files
│   └── pt_BR/
│       └── LC_MESSAGES/
│           ├── messages.po           # Portuguese translations
│           └── messages.mo           # Compiled translations
│
├── logs/                             # Application logs
│
├── alembic.ini                       # Alembic migration config
├── babel.cfg                         # Babel i18n extraction config
├── package.json                      # Node.js dependencies
├── postcss.config.js                 # PostCSS configuration (Tailwind)
├── pyproject.toml                    # Python project metadata (future)
├── requirements.txt                  # Python dependencies
├── setup-tailwind.sh                 # Tailwind CSS setup script
├── start.py                          # Application startup script
├── translate.sh                      # i18n extraction/compilation script
├── Dockerfile                        # Docker container definition
├── compose.yml                       # Docker Compose configuration
├── .env.example                      # Environment variable template
├── .env                              # Environment variables (dev)
├── .gitignore                        # Git ignore rules
├── README.md                         # Project README
└── main.py                           # Entry point (redirects to app.main)
```

## 📦 Logical Organization

### Python Modules (app/)

**Core Files (Keep in app root):**
- `main.py` - FastAPI application definition and route handlers
- `config.py` - Configuration management with Pydantic
- `logger.py` - Logging setup
- `db.py` - SQLAlchemy engine and session management
- `models.py` - SQLModel table definitions
- `repository.py` - Data access layer (CRUD)
- `schemas.py` - Pydantic validation schemas
- `auth.py` - Session management and authentication
- `email.py` - Email service integration
- `i18n.py` - Translation utilities

**Subdirectories (For Future Expansion):**
- `api/` - Route modules (when main.py gets large, extract routes here)
- `core/` - Business logic and utilities (re-exports for clarity)
- `schemas/` - Organized schemas by domain (re-exports from schemas.py)
- `middleware/` - Custom middleware

### Templates (templates/)

**Hierarchy:**
- `_base.html` - Root template with HTML structure
- `components/` - Reusable components (buttons, forms, toggles)
- `pages/` - Full-page templates organized by feature
  - `auth/` - Authentication pages (login, register, verify email)
  - `admin/` - Admin panel pages (dashboard, user management)
  - `*.html` - Top-level pages (homepage, etc.)
- `layouts/` - Shared layouts (for future use)

### Static Files (static/)

**Organization:**
- `css/` - Stylesheets (Tailwind input + compiled output)
- `icons/` - SVG icons
- `images/` - Image assets
- `style.css` - Custom CSS

## 🔧 Why This Structure?

✅ **Scalability**: Easy to add new features without cluttering root directories
✅ **Clarity**: Each folder has a clear purpose
✅ **Separation of Concerns**: Templates, styles, and logic are separate
✅ **Team Collaboration**: Developers can work on different parts independently
✅ **Professional**: Follows FastAPI and web development best practices
✅ **Maintainability**: Easy to locate and modify code
✅ **Testing**: Clear separation makes testing easier
✅ **Future-Proof**: Can grow to complex applications without refactoring

## 🚀 Development Workflow

### Running the Application
```bash
python start.py
```
- Auto-runs database migrations
- Compiles translations
- Starts Uvicorn server on http://localhost:8000

### Building CSS
```bash
npm run build:css      # Build minified CSS
npm run watch:css      # Watch for changes and rebuild
```

### Managing Translations
```bash
./translate.sh extract  # Extract new strings
./translate.sh update   # Update translation files
./translate.sh refresh  # Extract + update + compile
./translate.sh compile  # Compile translations
```

### Database Migrations
```bash
alembic revision --autogenerate -m "Description"
alembic upgrade head    # Apply migrations
```

## 📋 Naming Conventions

- **Python files**: `snake_case.py`
- **Python classes**: `PascalCase`
- **Python functions**: `snake_case()`
- **HTML files**: `snake_case.html` or `kebab-case.html`
- **CSS classes**: `kebab-case`
- **Database tables**: `snake_case` (SQLModel handles)
- **Folders**: `lowercase`

## 🔀 Future Refactoring

As the project grows, consider:

1. **Extract routes into api/ modules:**
   - `api/contacts.py` - Contact CRUD routes
   - `api/auth.py` - Authentication routes
   - `api/admin.py` - Admin user management

2. **Expand core/ for shared logic:**
   - `core/exceptions.py` - Custom exceptions
   - `core/validators.py` - Validation utilities
   - `core/security.py` - Security utilities

3. **Add services/ layer:**
   - `services/email_service.py`
   - `services/user_service.py`
   - `services/auth_service.py`

4. **Create utils/ for helpers:**
   - `utils/decorators.py` - Custom decorators
   - `utils/date_utils.py` - Date/time helpers
   - `utils/string_utils.py` - String utilities

## 📚 Related Documentation

- [AUTHENTICATION.md](./AUTHENTICATION.md) - Auth system deep dive
- [MIGRATIONS.md](./MIGRATIONS.md) - Database migration guide
- [TAILWIND_SETUP.md](./TAILWIND_SETUP.md) - CSS build process
- [I18N.md](./I18N.md) - Multi-language support
