# AI Coding Agents Instructions for Project fastapi-alpine-starter

## Project Overview

This is a **FastAPI + Alpine.js + Tailwind CSS** starter template with full i18n support, async SQLModel persistence, and Tailwind CSS. The architecture favors **server-side rendering with progressive enhancement** via Alpine.js for client-side reactivity.

### Tech Stack
- **Backend**: FastAPI (async/await), Pydantic v2 validation, SQLModel (async SQLAlchemy)
- **Frontend**: Jinja2 templates, Alpine.js, Axios for AJAX calls, Tailwind CSS 4.x (PostCSS)
- **i18n**: Babel + Jinja2 i18n extension with context-aware locale handling
- **Database**: Async PostgreSQL (asyncpg) or SQLite (aiosqlite)
- **Testing**: pytest + pytest-asyncio with httpx AsyncClient

## Architecture Patterns

### 1. Repository Pattern with Async Sessions
- **Session management**: Use `get_session()` dependency from `app/repository.py` - it yields an `AsyncSession`
- **Repository functions**: All DB operations in `app/repository.py` take `AsyncSession` as first parameter
- Example: `await create_contact(session, payload)`, `await list_contacts(session, limit=10)`
- **Never** create sessions manually - always use the dependency injection pattern

### 2. Internationalization (i18n) Flow
- **Template strings**: Use `{{ _('Text') }}` in Jinja2 templates
- **Python code**: Import `from app.i18n import gettext as _` then use `_('Text')`
- **Client-side JS**: Inject translations server-side in templates: `errorMsg: "{{ _('Error message') }}"`
- **Locale detection**: Automatic from `Accept-Language` header + cookie persistence via `LocaleMiddleware`
- **After adding new strings**: Run `./translate.sh refresh` → edit `.po` files → `./translate.sh compile`
- Translation files live in `translations/{locale}/LC_MESSAGES/messages.po`

### 2.5 Model-Schema Separation (Development Contract)
- **MANDATORY**: Maintain strict separation between database models (`app/models/`) and API schemas (`app/schemas.py`)
- **Database Models** (`app/models/`): SQLModel classes inheriting from `SQLModel, table=True`
  - Handle data persistence, database constraints, foreign keys, indexes
  - Contain fields not exposed in APIs (e.g., internal timestamps, audit fields)
  - Example: `User(SQLModel, table=True)` with hashed_password, is_superuser fields
- **API Schemas** (`app/schemas.py`): Pure Pydantic classes inheriting from `BaseModel`
  - Define API request/response contracts and validation logic
  - Control data shapes for create vs read operations (e.g., exclude sensitive fields)
  - Contain API-specific validation with i18n-friendly error messages
  - Example: `UserRead(BaseModel)` with selected fields and `model_config = {"from_attributes": True}`
- **Why separated**:
  - Single Responsibility: Models handle persistence, schemas handle API contracts
  - Flexibility: Different validation rules for database vs API (stricter API validation)
  - Security: Exclude sensitive database fields from API responses
  - Evolution: Change API contracts without touching database schema (and vice versa)
- **Critical principle**: Always use schemas in FastAPI endpoints, never raw database models or `dict`
- **Base pattern**: Models use `{ModelName}Base(SQLModel)` classes for shared validation logic between models and schemas

### 3. Validation Strategy (Dual Client + Server)
- **Server-side**: Pydantic schemas in `app/schemas.py` with custom validators
- **Client-side**: Alpine.js `validate()` functions mirror server rules (see `_form_alpine.html`)
- **Error translation**: Pydantic validators use `_()` for i18n-friendly error messages
- When handling `ValidationError`, manually translate field errors for the user's locale (see `app/main.py` contact endpoint)

#### Form Validation Contract (CRITICAL)
- **MANDATORY**: All HTML forms MUST use `novalidate` attribute to disable native browser validation
- **Custom Validation**: Implement Alpine.js validation functions for all form fields
- **Validation Pattern**: Follow the pattern in `templates/components/_contact_form.html`:
  ```html
  <form @submit.prevent="submitForm" novalidate class="...">
    <input x-model="form.fieldName"
           @blur="validate('fieldName')"
           @input="validate('fieldName')"
           required />
    <div x-show="errors.fieldName" x-transition class="mt-2 flex items-center text-sm text-red-600">
      <svg class="h-4 w-4 mr-1">...</svg>
      <span x-text="errors.fieldName"></span>
    </div>
  </form>
  ```
- **Alpine Validation Function**: Implement `validate(field)` method with i18n support:
  ```javascript
  validate(field) {
    const value = this.form[field]?.trim() || '';
    if (!value) {
      this.errors[field] = this.i18n.fieldRequired;
    } else {
      this.errors[field] = '';
    }
  }
  ```
- **Why NO native validation**:
  - Native browser tooltips are inconsistent across browsers
  - Cannot be styled to match design system
  - Don't support dark mode properly
  - Don't support i18n translations
  - Create poor UX with floating tooltips
- **Benefits of custom validation**:
  - Consistent inline error messages below fields
  - Full Tailwind CSS styling support
  - Dark mode compatible
  - i18n translation support via `{{ _('...') }}`
  - Better visual integration with icons and transitions
- **Reference Examples**:
  - `templates/components/_contact_form.html` (contact form)
  - `templates/pages/profile.html` (profile and password forms)
  - `templates/pages/auth/register.html` (registration form)

### 4. API Validation Contract (CRITICAL)
- **MANDATORY**: All FastAPI endpoints accepting user data MUST use proper Pydantic validation schemas, NEVER raw `dict`
- **CREATE endpoints**: Use `{Model}Base` schema (e.g., `car_data: CarBase`, `book_data: BookBase`)
- **UPDATE endpoints**: Use `{Model}Base` schema with `exclude_unset=True` for partial updates
- **NEVER use**: `dict` type for user input - it bypasses ALL validation and allows invalid data
- **Example CORRECT**:
  ```python
  @app.post("/api/cars") async def create_car(car_data: CarBase, ...):  # ✅ VALIDATES
  @app.put("/api/cars/{id}") async def update_car(car_id: int, car_data: CarBase, ...):  # ✅ VALIDATES
  ```
- **Example WRONG**:
  ```python
  @app.post("/api/cars") async def create_car(car_data: dict, ...):  # ❌ BYPASSES VALIDATION
  @app.put("/api/cars/{id}") async def update_car(car_id: int, car_data: dict, ...):  # ❌ BYPASSES VALIDATION
  ```
- **Validation errors**: Return 422 status with field-specific Pydantic error details for datagrid components
- **Critical incident**: Cars edit/update modal bypassed validation because update endpoint used `dict` instead of `CarBase`
- **Testing**: Always test with invalid data (empty strings, wrong types) to ensure validation triggers

#### Custom Validation Error Messages (CRITICAL)
- **Problem**: Pydantic's `description` parameter in `Field()` is **only for API documentation**, NOT for validation error messages
- **Wrong approach**: Using built-in constraints like `Field(ge=1, description="Must be at least 1")` - the description is ignored for validation errors
- **Correct approach**: Use `@field_validator` decorators with translated error messages
- **Example WRONG**:
  ```python
  year: int = Field(ge=1, description="Year must be at least 1")  # ❌ description not used in errors
  price: float = Field(gt=0, description="Price must be positive")  # ❌ generic English error shown
  ```
- **Example CORRECT**:
  ```python
  year: int = Field()  # No constraint here

  @field_validator("year")
  @classmethod
  def validate_year(cls, v: int) -> int:
      if v < 1:
          from .i18n import gettext as _
          raise ValueError(_("Year must be at least 1"))  # ✅ Translatable custom message
      return v
  ```
- **Why this matters**:
  - Built-in Pydantic constraints (`ge`, `gt`, `lt`, `le`) always return **generic English messages**
  - These messages bypass translation system and show in English regardless of user locale
  - Custom validators with `_()` enable proper i18n support for all validation errors
- **Critical incident**: Books/Cars modals showed "Input should be greater than or equal to 1" in English instead of translated messages because validators used `Field(ge=1, description="...")` instead of `@field_validator`
- **Additional notes**:
  - `description` parameter is still useful for OpenAPI/Swagger documentation
  - For datagrid modals: ensure `translateError()` in `datagrid.js` handles `value_error` type by returning the original message (custom validator errors use this type)

### 6. Strategy Patterns (app/strategies.py)
- **Purpose**: Reduces CC in endpoints via polymorphism (ValidationErrorStrategy, AuthVerifier).
- **Validation**: `from .strategies import handle_validation_error`; `errors = handle_validation_error(e)` - registry maps msg/field to translated str.
  - Extend: Add `(snippet, field): MyStrategy()` to VALIDATION_REGISTRY.
  - Benefit: CC -8 in contact/register/etc., i18n centralized.
- **Auth**: `verifier = create_admin_login_verifier(user)`; `verifier.verify(password)` - combines user/role/pw/active.
  - Benefit: CC -4 in admin_login, extensible to other roles.
- Used in `app/main.py` top5 complex funcs post-audit.

### 7. Global User Context (Single Source of Truth)
- **Problem**: Inconsistent user data availability across templates (some routes passed `user`, others `current_user`, or nothing).
- **Solution**: Global dependency `inject_user_to_request_state` in `app/main.py`.
- **Mechanism**:
  - Runs for **every** request via `FastAPI(dependencies=[Depends(inject_user_to_request_state)])`.
  - Uses `fastapi-users`'s `current_user_optional` to get the authenticated user (or None).
  - Injects user into `request.state.user`.
- **Usage in Templates**:
  - **Preferred**: Use `request.state.user` (always available).
  - **Fallback**: Templates like `_top_navbar.html` check `user` (explicitly passed) OR `request.state.user`.
- **Benefit**: "Single Source of Truth" for user data without repeating code in every route handler.

### 4. Tailwind CSS Build Process
- **Version**: Tailwind CSS v4 via `@tailwindcss/postcss` plugin
- **Source**: `static/css/input.css` (uses `@import "tailwindcss"` instead of `@tailwind` directives)
- **Output**: `static/css/output.css` (compiled via PostCSS, auto-generated)
- **Configuration**: `postcss.config.js` with `@tailwindcss/postcss`, `postcss-nesting`, and `autoprefixer`
- **No tailwind.config.js**: V4 uses CSS-based configuration, don't create `tailwind.config.js`
- **Dark mode**: Class-based with `@custom-variant dark (&:where(.dark, .dark *))` in `input.css`
- **Development**: `npm run watch:css` in separate terminal (auto-rebuilds on template changes)
- **Production/Docker**: `npm run build:css` (minified with cssnano)
- **V4 syntax**: Use `@import "tailwindcss";` instead of old `@tailwind base/components/utilities`
- **Never** edit `output.css` directly - modify `input.css` or use Tailwind classes in templates

### 5. Toast Notification System
- **Library**: Custom implementation in `static/js/toast.js` (dependency-free, vanilla JS)
- **Styling**: Tailwind CSS v4 with premium aesthetics (white/dark surface, accent borders, deep shadows)
- **Global Access**: Available on every page via `window.showToast(message, type)`
- **Usage**:
  ```javascript
  // Types: 'success', 'error', 'warning', 'info'
  window.showToast('Operation successful', 'success');
  window.showToast('{{ _("Translated error message") }}', 'error');
  ```
- **Initialization**: Configured in `_base.html` with i18n support:
  ```javascript
  window.Toast.init({
      translations: {
          close: "{{ _('Close') }}"
      }
  });
  ```
- **Features**:
  - Auto-dismiss with visual progress bar (3 seconds default)
  - Fixed width (`w-80` mobile, `w-96` desktop) to prevent squashing
  - Absolute positioning for close button to avoid text overlap
  - Dark mode support
- **Best Practice**: Always use server-side translation (`{{ _('...') }}`) for toast messages passed from templates.

## Critical Workflows

### Development Setup
```bash
# 1. Python environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Build Tailwind (required before first run)
npm install && npm run build:css

# 3. Compile translations (required for i18n)
./translate.sh compile

# 4. Create dev database
python -m app.create_db

# 5. Run app
uvicorn app.main:app --reload --proxy-headers
```

### Adding New Features with i18n
1. Add user-facing strings with `_('...')` in templates/code
2. Extract: `./translate.sh extract`
3. Update locales: `./translate.sh update`
4. Edit `translations/*/LC_MESSAGES/messages.po` files
5. Compile: `./translate.sh compile`
6. Test in both languages (switch via globe icon or cookie)

### Database Migrations
- **Development**: `python -m app.create_db` (calls `SQLModel.metadata.create_all`)
- **Production**: Use Alembic - see `MIGRATIONS.md` and `alembic/versions/` for examples
- Never use `create_db` in production - it doesn't handle schema evolution

## Project-Specific Conventions

### File Organization & Folder Structure

The project uses a professional, enterprise-grade folder organization that supports scalability and team collaboration:

```
app/                        # Application core (Python modules)
  ├── main.py               # FastAPI app initialization & routes
  ├── config.py             # Configuration (Pydantic BaseSettings)
  ├── models.py             # SQLModel table definitions
  ├── schemas.py            # Pydantic validation schemas
  ├── repository.py         # Data access layer (CRUD operations)
  ├── auth.py               # Session management & authentication
  ├── email.py              # resend email service integration
  ├── i18n.py               # i18n translation utilities
  ├── logger.py             # Loguru logging configuration
  ├── db.py                 # Database engine & session management
  └── create_db.py          # Database initialization for development

templates/                   # Jinja2 templates (organized by feature)
  ├── _base.html            # Root template (HTML structure, common elements)
  ├── components/           # Reusable template components
  │   ├── _theme_toggle.html
  │   ├── _language_selector.html
  │   └── _contact_form.html (forms with Alpine.js validation)
  └── pages/                # Full-page templates
      ├── index.html
      ├── auth/             # Authentication pages
      │   ├── login.html
      │   ├── register.html
      │   └── check_email.html
      └── admin/            # Admin panel pages
          ├── login.html
          ├── index.html
          └── users.html

static/                      # Static assets
  ├── css/                  # Stylesheets
  │   ├── input.css         # Tailwind source (DO NOT edit output.css)
  │   └── output.css        # Compiled CSS (auto-generated)
  ├── icons/                # SVG icons (Heroicons)
  ├── images/               # Image assets
  └── style.css             # Custom CSS overrides

docs/                        # Project documentation
  ├── ARCHITECTURE.md       # Folder structure & design decisions
  ├── AUTHENTICATION.md     # Auth system implementation
  ├── MIGRATIONS.md         # Database migrations guide
  ├── TAILWIND_SETUP.md     # CSS build process
  └── I18N.md               # i18n implementation details
```

**Key Organization Principles:**
- **app/** - All Python logic (routes, models, database access)
- **templates/** - HTML templates, organized by feature/area
- **static/css/** - CSS files (input source and compiled output separate)
- **docs/** - All documentation files (NEVER in root directory)

**When Adding New Files:**
- Python modules → `app/`
- Page templates → `templates/pages/{feature}/`
- Reusable components → `templates/components/`
- CSS changes → Edit `static/css/input.css`, rebuild with `npm run build:css`
- Documentation → Always use `docs/` folder

- `app/main.py`: FastAPI app, routes, middleware setup
- `app/models.py`: SQLModel table definitions (inherit from `SQLModel, table=True`)
- `app/schemas.py`: Pydantic validation schemas (separate from DB models)
- `app/repository.py`: All database queries (session dependency + CRUD functions)
- `app/i18n.py`: Translation utilities (context-based locale storage)
- `templates/_*.html`: Reusable partials (forms, components)
- **AJAX Library**: Axios is the standard for all AJAX calls - never use fetch() - see AJAX section below
- **Documentation**: ALL `.md` files and guides must be placed in `docs/` folder, NEVER in root directory. Examples: `docs/AUTHENTICATION.md`, `docs/MIGRATIONS.md`, `docs/SETUP_GUIDE.md`

### Jinja2 Template Patterns
- **Template engine**: Jinja2 configured in `app/main.py` with i18n extension enabled
- **Base template**: `_base.html` includes Alpine.js CDN, theme toggle, toast system, common scripts
- **Template inheritance**: Use `{% extends "_base.html" %}` and `{% block content %}...{% endblock %}`
- **Partials**: Prefixed with `_` and included via `{% include "_partial.html" %}`
- **i18n in templates**: Use `{{ _('Text to translate') }}` for all user-facing strings
- **Request context**: Always pass `request` to templates: `templates.TemplateResponse("page.html", {"request": request, ...})`
- **Alpine components**: Defined as `x-data="componentName()"` with inline `<script>` functions
- **i18n in Alpine.js**: Inject translations server-side into `i18n` object: `i18n: { key: "{{ _('Value') }}" }`
- **Dynamic values**: Use Jinja2 variables: `{{ contact.name }}`, access via dot notation or filters

### AJAX Library (Axios)
- **Standard Library**: Always use Axios for AJAX calls, never fetch()
- **CDN Loading**: Axios is loaded globally in `_base.html` - available in all templates
- **Error Handling**: Axios throws exceptions on HTTP errors - use try/catch:
  ```javascript
  try {
    const response = await axios.post('/api/endpoint', formData, {
      headers: { 'Accept': 'application/json' }
    });
    const data = response.data;
    // Success handling
  } catch (error) {
    if (error.response && error.response.data) {
      // Handle server errors
    }
    // Handle network/other errors
  }
  ```
- **Content Types**:
  - Form submissions: `axios.post(url, formData)` (FormData automatically sets multipart)
  - JSON responses: `headers: { 'Accept': 'application/json' }`
  - HTML responses: `headers: { 'Accept': 'text/html' }` + `response.data` for HTML string
- **Standard Patterns**: See existing templates for examples (contact form, auth login, etc.)

### Logging
- Use `from app.logger import get_logger` then `logger = get_logger("module_name")`
- Loguru with structured format: `logger.info("Message: {}", variable)`
- Log level auto-adjusts: DEBUG in dev, INFO in production (based on `settings.debug`)

### Configuration
- All settings in `app/config.py` via Pydantic `BaseSettings` (reads `.env`)
- Required env vars: `DATABASE_URL`, `SECRET_KEY`, `ENV`
- Access via `from app.config import settings`

## Testing Patterns

- **Fixture**: `client` fixture provides `httpx.AsyncClient` with test database
- **Test DB**: Temporary SQLite file per session (`conftest.py`)
- **Async tests**: Decorate with `@pytest.mark.asyncio`
- **Form submissions**: `await client.post("/contact", data={...}, headers={"Accept":"text/html"})`
- Run tests: `pytest` (from project root)

## Docker Deployment

- **Dockerfile**: Multi-stage with Node.js for Tailwind build + translation compilation
- **compose.yml**: Single-service setup with SQLite (for dev/demo)
- Build process: `npm run build:css` → `pybabel compile` → run uvicorn
- Volume mount: `./:/app` for live reload in dev mode

## Common Pitfalls

1. **Missing `output.css`**: Causes styling to break - always run `npm run build:css` first
2. **Untranslated strings**: Remember to wrap ALL user-visible text in `_('...')`
3. **Locale context**: Set locale via middleware - don't call `set_locale()` manually in routes
4. **Session lifecycle**: Never `await session.close()` when using dependency injection
5. **Alpine.js state**: Initialize with `x-init="init()"` to handle server-rendered errors
6. **Form validation**: Keep client-side rules in sync with Pydantic validators
7. **Global i18n objects**: Never initialize global objects (like `window.datagridI18n`) inside `DOMContentLoaded` - they must be available BEFORE Alpine.js loads. Alpine components with `defer` scripts may initialize before `DOMContentLoaded` fires, causing `undefined` references. Initialize globals synchronously in `<script>` tags in the `<head>`.
8. **Pydantic validation messages**: Never use `Field(ge=1, description="...")` for custom error messages - the `description` is only for API docs. Use `@field_validator` decorators with `_("...")` for translatable validation errors. Built-in constraints (`ge`, `gt`, `le`, `lt`) return generic English messages that bypass i18n.

## Frontend Performance & FOUC Prevention

This project implements critical optimizations to eliminate Flash of Unstyled Content (FOUC) and layout shifts:

### 1. SVG Icon Sizing (Preventing Huge Icon Flash)
- **Problem**: SVG icons without native `width`/`height` attributes render at their intrinsic size (often huge) before CSS loads
- **Solution**: Add explicit `width` and `height` attributes to ALL SVG elements
- **Implementation**:
  ```html
  <svg class="w-5 h-5"
       width="20" height="20"  <!-- Native HTML attributes for immediate sizing -->
       aria-hidden="true"
       xmlns="http://www.w3.org/2000/svg"
       fill="currentColor"
       viewBox="0 0 20 20">
  ```
- **Why**: Native HTML attributes apply synchronously as the DOM parses, before CSS loads. Tailwind classes (`w-5 h-5`) are a secondary refinement.
- **Coverage**: Apply to all SVG icons in:
  - `templates/components/_sidebar.html` (navigation icons)
  - `templates/components/_top_navbar.html` (profile menu, hamburger)
  - `templates/components/_theme_toggle.html` (theme icons)
  - `templates/components/_language_selector.html` (language icons)

### 2. CSS-First Loading (Preventing General FOUC)
- **Problem**: Scripts load before CSS, causing components to render unstyled then restyle when CSS arrives
- **Solution**: Load CSS before all JavaScript (especially Alpine.js)
- **Order in `_base.html`**:
  ```html
  <head>
      <!-- ... meta tags, preconnect, fonts ... -->
      <!-- CSS BEFORE scripts -->
      <link rel="stylesheet" href="/static/css/output.css">
      <link rel="stylesheet" href="/static/style.css" />

      <!-- Scripts AFTER CSS -->
      <script defer src="/static/js/axios.min.js"></script>
      <script defer src="/static/js/datagrid.js"></script>
      <!-- Alpine.js loads last -->
      <script defer src="/static/js/alpine-min.js"></script>
  </head>
  ```
- **Why**: By the time Alpine.js initializes, external CSS is already loaded and parsed.

### 3. Dark Mode White Flash Prevention (Critical Theme Script)
- **Problem**: If dark mode was the last-used theme, a white flash appears on page load before dark styles apply
- **Root cause**: Theme detection runs too late, after body's default light background is painted
- **Solution**:
  1. Move theme detection to **very top of `<head>`** - run BEFORE any stylesheets
  2. Add **critical inline styles** that apply dark background immediately based on `.dark` class
- **Implementation**:
  ```html
  <head>
      <!-- CRITICAL: Run synchronously at very start of head -->
      <script>
          (function() {
              if (localStorage.getItem('theme') === 'dark') {
                  document.documentElement.classList.add('dark');
              }
          })();
      </script>
      <!-- Critical inline styles apply before external CSS loads -->
      <style>
          html { background-color: #f9fafb; } /* gray-50 - light mode default */
          html.dark { background-color: #111827; } /* gray-900 - dark mode */
          body { background-color: inherit; margin: 0; }
      </style>

      <!-- Preconnect, fonts -->
      <link rel="preconnect" href="https://fonts.googleapis.com">

      <!-- CSS loads after theme is set -->
      <link rel="stylesheet" href="/static/css/output.css">
  </head>
  ```
- **Why**:
  - Inline styles apply **immediately** as HTML parses
  - `.dark` class is already on `<html>` when background is first painted
  - External CSS refines the styles but doesn't cause repaints
  - Timeline: Script runs → Class added → Inline CSS applies → First paint (dark) → External CSS loads (no repaint)

### Key Principle: Synchronous vs Asynchronous

All FOUC prevention relies on **synchronous execution before first paint**:
- ✅ **Synchronous** (applies before paint): Inline `<script>`, inline `<style>`, native HTML attributes
- ❌ **Asynchronous** (applies after paint): External scripts with `defer`, external stylesheets, JavaScript DOM manipulation

Always prioritize synchronous approaches for critical styling/layout attributes.

### 4. Alpine.js x-cloak Directive (Preventing Empty Element Flash)
- **Problem**: Elements using `x-show` are visible by default before Alpine.js initializes, causing empty alert boxes, error icons, or loading spinners to flash briefly
- **Solution**: Add `x-cloak` directive to ALL elements that should be hidden initially
- **How it works**:
  - CSS rule `[x-cloak] { display: none; }` in `static/css/input.css` hides elements immediately
  - When Alpine initializes, it removes the `x-cloak` attribute
  - Then `x-show` takes over to control visibility
- **Implementation**:
  ```html
  <!-- ✅ CORRECT: x-cloak prevents flash before Alpine loads -->
  <div x-cloak x-show="errorMessage" class="alert-error">...</div>
  <div x-cloak x-show="loading" class="spinner">...</div>
  <div x-cloak x-show="errors.email" class="error-with-icon">...</div>

  <!-- ❌ WRONG: Element flashes visible before Alpine hides it -->
  <div x-show="errorMessage" class="alert-error">...</div>
  ```
- **When to use `x-cloak`**:
  - Alert/notification boxes (`x-show="successMessage"`, `x-show="errorMessage"`)
  - Form field validation errors (`x-show="errors.fieldName"`)
  - Loading spinners (`x-show="loading"`)
  - Dropdowns and modals (`x-show="open"`)
  - Any element that starts hidden and appears conditionally
- **When NOT to use `x-cloak`**:
  - Elements that should be visible by default (`x-show="!loading"` for default button text)
  - Static content that doesn't depend on Alpine state
- **Reference**: See `templates/pages/auth/login.html` and `templates/pages/admin/login.html` for proper usage

## Key Commands Reference

| Task                | Command                         |
| ------------------- | ------------------------------- |
| Run dev server      | `uvicorn app.main:app --reload` |
| Watch Tailwind      | `npm run watch:css`             |
| Run tests           | `pytest`                        |
| Add locale          | `./translate.sh init pt_BR`     |
| Update translations | `./translate.sh refresh`        |
| Create dev DB       | `python -m app.create_db`       |
| Migration (prod)    | `alembic upgrade head`          |
| Docker build        | `docker-compose up --build`     |

## When Modifying This Codebase

- **Adding routes**: Follow the pattern in `app/main.py` - use dependency injection for `session`
- **New models**: Add to `app/models.py` (table) + `app/schemas.py` (validation)
- **New templates**: Organize by feature:
  - Page templates: `templates/pages/{feature}/page.html`
  - Auth pages: `templates/pages/auth/login.html`, `templates/pages/auth/register.html`
  - Admin pages: `templates/pages/admin/users.html`, `templates/pages/admin/index.html`
  - Reusable components: `templates/components/_component_name.html`
  - Extend from `_base.html`, use Tailwind classes, wrap strings in `_('...')`
  - Always pass `request` in template context: `{"request": request, ...}`
  - Use `{% block title %}`, `{% block content %}`, `{% block extra_head %}` for customization
- **Alpine components**: Define state/methods in inline `<script>` with `i18n` object for translations
- **CSS changes**: Edit `static/css/input.css` or add Tailwind classes (never edit `static/css/output.css`)
- **Jinja2 configuration**: Template globals/filters configured in `app/main.py` via `templates.env`

## Modern CLI Tool Protocol

When exploring the codebase or generating shell commands, prioritize the following modern, high-performance tools over legacy counterparts (like `find`, `grep`, `sed`).

### Tool Preference Mapping
* **File Search:** Use `fd` (instead of `find`).
    * *Benefit:* Respects .gitignore by default, faster.
* **Text/Regex Search:** Use `rg` (ripgrep).
    * *Benefit:* Faster, ignores binary files/git folder automatically.
* **Structural Code Search:** Use `ast-grep` (binary: `sg`).
    * *Benefit:* Understands syntax/AST, better than regex for code patterns.
* **JSON Processing:** Use `jq`.
* **YAML/XML Processing:** Use `yq`.
* **Interactive Selection:** Use `fzf` (only when writing scripts for the USER to run; do not run `fzf` inside non-interactive agent sessions).

### Execution Rules
1.  **Check Availability:** Before running a complex command, ensure the tool exists (e.g., `command -v rg`).
2.  **Fallback:** If the modern tool is missing, fall back to standard POSIX tools (`find`, `grep`, `sed`).
3.  **Flags:** Use flags that produce machine-readable output when you need to parse the result (e.g., `rg --json` or `fd -0`).
