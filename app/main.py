from contextlib import asynccontextmanager
from datetime import datetime
from json import JSONEncoder
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates  # type: ignore[import]
from pydantic import ValidationError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from .auth import (
    COOKIE_NAME,
    create_session_cookie,
    require_admin,
)
from .config import settings
from .db import init_db
from .email import (
    send_registration_notification,
)
from .grid_engine import GridEngine, PaginatedResponse
from .i18n import get_locale, get_translations, set_locale
from .i18n import gettext as _
from .logger import get_logger
from .models import Book, BookBase, Car, CarBase, Contact, User, UserRole
from .repository import (
    create_contact,
    create_user,
    get_recent_contacts,
    get_session,
    get_user_by_email,
    get_valid_token,
    list_contacts,
    list_users,
    mark_token_used,
    seed_cars,
)
from .response_helpers import ResponseHelper
from .schemas import (
    ContactCreate,
    LoginRequest,
    UserRegister,
)

logger = get_logger("main")


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await init_db()
        logger.info("DB initialized on startup")

        # Seed cars if needed
        from .db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await seed_cars(session, count=500)
    except Exception as e:
        logger.error("Startup failed: {}", e)
    yield
    # Shutdown (if needed in the future)


class DateTimeJSONEncoder(JSONEncoder):
    """Custom JSON encoder for datetime objects"""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
    json_encoders={datetime: lambda v: v.isoformat()},
)

# Add GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

templates = Jinja2Templates(directory="templates")

# Configure Jinja2 with i18n extension
templates.env.add_extension("jinja2.ext.i18n")
templates.env.install_gettext_callables(
    gettext=lambda x: get_translations(get_locale()).gettext(x),
    ngettext=lambda s, p, n: get_translations(get_locale()).ngettext(s, p, n),
    newstyle=True,
)


# Global template context for all templates
def get_template_context():
    """Get global context for all templates."""
    return {"enable_i18n": settings.ENABLE_I18N}


# Add global context function to templates
templates.env.globals.update(get_template_context())

# Mount static files with caching (1 year for immutable assets)
app.mount("/static", StaticFiles(directory="static", html=False), name="static")


# Middleware for locale detection
class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from .locale import default_locale_resolver

        locale = default_locale_resolver.resolve_locale(request)

        # Set locale for this request
        set_locale(locale)

        # Make locale available in request state
        request.state.locale = locale

        response = await call_next(request)
        return response


app.add_middleware(LocaleMiddleware)





class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """
    Custom exception handler for HTTP exceptions.

    Handles redirects for authentication errors (401) and returns JSON/HTML
    appropriate for the request type.
    """
    if exc.status_code == 401:
        # Check if it's an API request
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )

        # For HTML requests, redirect to appropriate login page
        from urllib.parse import quote

        next_url = quote(str(request.url), safe="")

        if request.url.path.startswith("/admin"):
            return RedirectResponse(
                url=f"/admin/login?next={next_url}", status_code=302
            )
        else:
            return RedirectResponse(
                url=f"/auth/login?next={next_url}", status_code=302
            )

    # For other errors, return JSON
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, session: AsyncSession = Depends(get_session)):
    recent_contacts = await get_recent_contacts(session, limit=4)
    response = templates.TemplateResponse(
        "pages/index.html",
        {
            "request": request,
            "recent_contacts": recent_contacts,
        },
    )
    # Cache headers for improved performance
    response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return response


@app.get("/recent-contacts", response_class=HTMLResponse)
async def get_recent_contacts_partial(
    request: Request, session: AsyncSession = Depends(get_session)
):
    """Return just the recent contacts partial for dynamic updates"""
    recent_contacts = await get_recent_contacts(session, limit=4)
    response = templates.TemplateResponse(
        "components/_recent_contacts.html",
        {"request": request, "recent_contacts": recent_contacts},
    )
    # Short cache since this data changes frequently
    response.headers["Cache-Control"] = "private, max-age=10"
    return response


@app.post("/contact")
async def contact(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    form_data = {"name": name, "email": email, "message": message}
    logger.info(
        "Form submission received: name={}, email={}, message_length={}",
        form_data["name"],
        form_data["email"],
        len(form_data["message"] or ""),
    )

    # Server-side validation with Pydantic
    try:
        payload = ContactCreate.model_validate(form_data)
        logger.info("Form validation successful for user: {}", form_data["email"])
    except ValidationError as e:
        logger.warning(
            "Form validation failed for: email={}, errors={}",
            form_data["email"],
            str(e),
        )
        # Return JSON for Alpine.js using helper
        return ResponseHelper.pydantic_validation_error(e, form_data)

    # Persist contact
    try:
        contact = await create_contact(session, payload)
        logger.info(
            "Contact successfully saved: email={}, id={}",
            form_data["email"],
            contact.id,
        )
    except Exception as exc:
        logger.error("Failed to save contact: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to save contact")

    # Return JSON for Alpine.js
    return JSONResponse(
        content={
            "success": True,
            "contact": {
                "id": contact.id,
                "name": contact.name,
                "email": contact.email,
                "message": contact.message,
            },
        }
    )


# ============= Data Grid Routes =============


@app.get("/contacts", response_class=HTMLResponse)
async def contacts_page(request: Request):
    """Display contacts directory page with data grid"""
    return templates.TemplateResponse(
        "pages/contacts.html",
        {
            "request": request,
            "api_url": "/api/contacts",
            "columns": [
                {"key": "id", "label": _("ID"), "width": 70, "sortable": True},
                {
                    "key": "name",
                    "label": _("Name"),
                    "width": 200,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "email",
                    "label": _("Email"),
                    "width": 250,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "message",
                    "label": _("Message"),
                    "width": 300,
                    "sortable": False,
                },
                {
                    "key": "created_at",
                    "label": _("Submitted"),
                    "width": 180,
                    "sortable": True,
                },
            ],
            "search_placeholder": _("Search by name or email..."),
        },
    )


@app.get("/api/contacts", response_model=PaginatedResponse[Contact])
async def get_contacts_grid(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "id",
    dir: str = "asc",
    session: AsyncSession = Depends(get_session),
):
    """API endpoint for contacts data grid with server-side pagination, filtering, and sorting"""
    grid = GridEngine(session, Contact)
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["name", "email"],
    )


@app.get("/api/admin/users", response_model=PaginatedResponse[User])
async def get_users_grid(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "id",
    dir: str = "asc",
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """API endpoint for users data grid (admin only)"""
    grid = GridEngine(session, User)
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["email", "full_name"],
    )


# ============= Authentication Routes =============


@app.get("/auth/register", response_class=HTMLResponse)
async def register_form(request: Request):
    """Display user registration form"""
    return templates.TemplateResponse(
        "pages/auth/register.html", {"request": request, "error": None}
    )


@app.post("/auth/register")
async def register(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    """Handle user self-registration (creates pending user)"""
    from .response_helpers import FormResponseHelper

    form_data = {"email": email, "full_name": full_name}

    # Check if user already exists
    existing_user = await get_user_by_email(session, email)
    if existing_user:
        return FormResponseHelper.form_error(
            message=_("An account with this email already exists"), form_data=form_data
        )

    # Validate with Pydantic
    try:
        payload = UserRegister.model_validate(form_data)
    except ValidationError as e:
        return FormResponseHelper.form_error(
            message=_("Registration failed"),
            field_errors=ResponseHelper.pydantic_validation_error(e),
        )

    # Create pending user
    try:
        user = await create_user(session, payload, role=UserRole.PENDING)
        logger.info(f"New user registered: {user.email} (pending approval)")

        # Send notification to admins
        admin_url = f"{settings.APP_BASE_URL}/admin/users"
        # Get first admin to notify (in production, notify all admins)
        admin_users = await list_users(session, role_filter=UserRole.ADMIN, limit=1)
        if admin_users:
            await send_registration_notification(
                admin_users[0].email, user.email, user.full_name, admin_url
            )

        return FormResponseHelper.form_success(
            message=_(
                "Registration successful! Your account is pending admin approval."
            )
        )
    except Exception as exc:
        logger.error(f"Failed to create user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create account")


@app.get("/auth/login", response_class=HTMLResponse)
async def login_form(request: Request):
    """Display magic link login form"""
    return templates.TemplateResponse(
        "pages/auth/login.html", {"request": request, "error": None}
    )


@app.post("/auth/login")
async def login(
    request: Request,
    email: str = Form(...),
    next: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Request magic link for passwordless login"""
    from .response_helpers import FormResponseHelper

    form_data = {"email": email}

    # Validate email format
    try:
        LoginRequest.model_validate(form_data)
    except ValidationError as e:
        return FormResponseHelper.form_error(
            message=_("Login failed"),
            field_errors=ResponseHelper.pydantic_validation_error(e),
        )

    from .auth_strategies import (
        AuthenticationRequest,
        default_auth_strategy,
    )

    # Use authentication strategy
    auth_request = AuthenticationRequest(email, session, next)
    response = await default_auth_strategy.handle_login(auth_request)

    if response:
        return response.to_response()

    # Redirect to check email page
    return templates.TemplateResponse(
        "pages/auth/check_email.html", {"request": request, "email": email}
    )


@app.get("/auth/verify/{token}")
async def verify_magic_link(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Verify magic link token and create session"""
    result = await get_valid_token(session, token)

    if not result:
        return templates.TemplateResponse(
            "pages/auth/login.html",
            {
                "request": request,
                "error": _("Invalid or expired login link. Please request a new one."),
            },
        )

    login_token, user = result

    # Mark token as used
    await mark_token_used(session, login_token)

    # Mark email as verified
    if not user.email_verified:
        user.email_verified = True
        await session.commit()

    # Create session cookie
    assert user.id is not None  # User should exist from get_valid_token
    cookie = create_session_cookie(user.id, user.email, user.role)

    # Redirect based on role or next URL
    redirect_url = "/admin" if user.role == UserRole.ADMIN else "/"

    # Check for next URL
    next_url = request.query_params.get("next")
    if next_url:
        from .url_validator import validate_admin_redirect
        # Validate redirect URL to prevent open redirects
        # We use validate_admin_redirect but it works for general URLs too if we want strict checking
        # Or we can implement a more general validator
        redirect_url = validate_admin_redirect(next_url, redirect_url)

    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        cookie,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,  # Use secure cookies in production
    )

    logger.info(f"User logged in via magic link: {user.email}")
    return response


@app.get("/auth/logout")
async def logout():
    """Log out current user"""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ============= Admin Routes (Password login for bootstrap admin only) =============


# Simple login form for admin (development). For production, use proper auth.
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_form(request: Request):
    """Display admin login form with optional 'next' parameter for post-login redirect"""
    return templates.TemplateResponse(
        "pages/admin/login.html", {"request": request, "error": None}
    )


# Safe URL passthrough for JS - avoids Jinja2 escaping issues
@app.get("/admin/login-url")
async def admin_login_url(request: Request, next: Optional[str] = None):
    """Return just the next URL safely for JavaScript"""
    from urllib.parse import unquote

    if next:
        try:
            decoded = unquote(next)
            # Basic validation
            from urllib.parse import urlparse

            parsed = urlparse(decoded)
            if (
                parsed.scheme == ""
                and parsed.netloc == ""
                and parsed.path.startswith("/admin")
            ):
                return {"next_url": decoded}
        except Exception:
            pass
    return {"next_url": ""}


@app.post("/admin/login")
async def admin_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: Optional[str] = None,  # From query parameter (middleware)
    session: AsyncSession = Depends(get_session),
):
    """Bootstrap admin login with password (admin only)"""
    from .admin_services import AdminLoginService, InvalidCredentialsError

    form_data = {"email": email, "password": password}

    login_service = AdminLoginService(session)

    try:
        # Authenticate user using service with guard clauses
        result = await login_service.authenticate(email, password, next)

        # Return success response - JavaScript will handle redirect
        response = JSONResponse(
            content={"success": True, "redirect_url": result.redirect_url}
        )

        # Set session cookie on response
        response.set_cookie(
            COOKIE_NAME,
            result.session_cookie,
            httponly=True,
            samesite="lax",
            secure=not settings.debug,
        )

        logger.info(f"Bootstrap admin logged in: {result.user.email}")
        return response

    except InvalidCredentialsError:
        # Return standardized error response using helper
        return ResponseHelper.validation_error(
            {"email": _("Invalid credentials")}, form_data
        )


@app.get("/admin", response_class=HTMLResponse)
async def admin_index(
    request: Request,
    session=Depends(require_admin),
    session_db: AsyncSession = Depends(get_session),
):
    # show list of contacts
    contacts = await list_contacts(session_db, limit=100)
    return templates.TemplateResponse(
        "pages/admin/index.html", {"request": request, "contacts": contacts}
    )


@app.post("/admin/contact/delete", response_class=HTMLResponse)
async def admin_delete_contact(
    request: Request,
    id: int = Form(...),
    session=Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    # simple delete operation
    await db.execute(__import__("sqlmodel").sql.delete(Contact).where(Contact.id == id))
    await db.commit()
    return RedirectResponse(url="/admin", status_code=303)


# ============= Admin Cars Routes =============


@app.get("/admin/cars", response_class=HTMLResponse)
async def admin_cars(
    request: Request,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin page for cars inventory - publicly accessible"""
    return templates.TemplateResponse(
        "pages/admin/cars.html",
        {
            "request": request,
            "current_user": current_user,
        },
    )


@app.get("/api/admin/cars", response_model=PaginatedResponse[Car])
async def get_admin_cars(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "id",
    dir: str = "asc",
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """API endpoint for cars grid"""
    grid = GridEngine(session, Car)
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["make", "model", "version", "year", "price"],
    )


@app.post("/api/admin/cars", response_model=Car)
async def create_car(
    car_data: CarBase,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Create a new car"""
    from app.logger import logger
    logger.info(f"Creating car with data: {car_data}")

    # Create Car instance from validated CarBase data
    car = Car(**car_data.model_dump())
    session.add(car)
    await session.commit()
    await session.refresh(car)
    return car


@app.put("/api/admin/cars/{car_id}", response_model=Car)
async def update_car(
    car_id: int,
    car_data: CarBase,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing car"""
    result = await session.execute(select(Car).where(Car.id == car_id))
    car = result.scalar_one_or_none()

    if not car:
        raise HTTPException(status_code=404, detail="Car not found")

    # Only update fields that were provided (exclude_unset=True)
    update_data = car_data.model_dump(exclude_unset=True)
    protected_fields = {"id", "created_at"}

    for key, value in update_data.items():
        if key not in protected_fields and hasattr(car, key):
            setattr(car, key, value)

    await session.commit()
    await session.refresh(car)
    return car


@app.delete("/api/admin/cars/{car_id}")
async def delete_car(
    car_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a car"""
    # First check if the car exists
    result = await session.execute(select(Car).where(Car.id == car_id))
    car = result.scalar_one_or_none()

    if not car:
        raise HTTPException(status_code=404, detail="Car not found")

    try:
        # Use raw SQL delete with proper SQLAlchemy import
        from sqlalchemy import delete

        await session.execute(delete(Car).where(Car.id == car_id))
        await session.commit()

        # Verify deletion by checking if car still exists
        verify_result = await session.execute(select(Car).where(Car.id == car_id))
        if verify_result.scalar_one_or_none() is not None:
            await session.rollback()
            raise HTTPException(
                status_code=500, detail="Failed to delete car from database"
            )

        logger.info(
            f"Successfully deleted car ID {car_id}: {car.make} {car.model} ({car.year})"
        )
        return {"success": True, "message": "Car deleted successfully"}

    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete car ID {car_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete car: {str(e)}")


# ============= Book Routes (Universal Grid Demo) =============


@app.get("/books", response_class=HTMLResponse)
async def books_page(request: Request):
    """Display books page with universal data grid"""
    return templates.TemplateResponse(
        "pages/books.html",
        {
            "request": request,
            "api_url": "/api/books",
            # Note: We don't strictly need to pass columns here if the frontend
            # could also auto-detect, but for now we define frontend columns manually.
            # The backend GridEngine WILL auto-detect search fields.
            "columns": [
                {"key": "id", "label": _("ID"), "width": 70, "sortable": True},
                {"key": "title", "label": _("Title"), "width": 250, "sortable": True, "filterable": True},
                {"key": "author", "label": _("Author"), "width": 200, "sortable": True, "filterable": True},
                {"key": "year", "label": _("Year"), "width": 100, "sortable": True, "filterable": True},
                {"key": "pages", "label": _("Pages"), "width": 100, "sortable": True},
                {"key": "summary", "label": _("Summary"), "width": 300, "sortable": False},
            ],
        },
    )


@app.get("/api/books", response_model=PaginatedResponse[Book])
async def get_books_grid(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "id",
    dir: str = "asc",
    session: AsyncSession = Depends(get_session),
):
    """API endpoint for books grid - demonstrating auto-detection of search fields"""
    grid = GridEngine(session, Book)
    # Note: We do NOT pass search_fields here to test auto-detection!
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
    )


@app.post("/api/books", response_model=Book)
async def create_book(
    book_data: BookBase,
    session: AsyncSession = Depends(get_session),
):
    """Create a new book with validation via BookBase"""
    from app.logger import logger
    logger.info(f"Creating book with data: {book_data}")

    # Create Book instance from validated BookBase data
    book = Book(**book_data.model_dump())
    session.add(book)
    await session.commit()
    await session.refresh(book)
    return book


@app.put("/api/books/{book_id}", response_model=Book)
async def update_book(
    book_id: int,
    book_data: BookBase,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing book with validation via BookBase"""
    result = await session.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Only update fields that were provided (exclude_unset=True)
    update_data = book_data.model_dump(exclude_unset=True)
    protected_fields = {"id", "created_at"}

    for key, value in update_data.items():
        if key not in protected_fields and hasattr(book, key):
            setattr(book, key, value)

    await session.commit()
    await session.refresh(book)
    return book


@app.delete("/api/books/{book_id}")
async def delete_book(
    book_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a book"""
    result = await session.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    await session.delete(book)
    await session.commit()
    return {"success": True, "message": "Book deleted successfully"}


# ============= Admin User Management Routes =============


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_list(
    request: Request,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin page to manage users"""
    users = await list_users(session, limit=200)
    return templates.TemplateResponse(
        "pages/admin/users.html",
        {"request": request, "users": users, "current_user": current_user},
    )


@app.post("/admin/users/{user_id}/approve")
async def admin_approve_user(
    user_id: int,
    role: UserRole = Form(UserRole.USER),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Approve a pending user and set their role"""
    from .admin_services import UserManagementService
    from .response_helpers import FormResponseHelper

    user_service = UserManagementService(session)

    try:
        # Approve user using service with proper validation
        approved_user = await user_service.approve_user(user_id, role, current_user)

        # Return success response using helper
        return FormResponseHelper.form_success(
            message=_("User approved successfully"),
            user={
                "id": approved_user.id,
                "email": approved_user.email,
                "full_name": approved_user.full_name,
                "role": approved_user.role.value,
                "is_active": approved_user.is_active,
                "email_verified": approved_user.email_verified,
            },
        )
    except Exception as exc:
        logger.error(f"Failed to approve user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to approve user")


@app.post("/admin/users/create")
async def admin_create_user(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    role: UserRole = Form(...),
    password: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin creates a new user with optional password"""
    from .admin_services import UserManagementService
    from .response_helpers import FormResponseHelper

    user_service = UserManagementService(session)

    try:
        # Create user using service with proper validation
        created_user = await user_service.create_user(
            email, full_name, role, password, current_user
        )

        # Return success response using helper
        return FormResponseHelper.form_success(
            message=_("User created successfully"),
            user={
                "id": created_user.id,
                "email": created_user.email,
                "full_name": created_user.full_name,
                "role": created_user.role.value,
                "is_active": created_user.is_active,
            },
        )
    except Exception as exc:
        logger.error(f"Failed to create user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create user")


@app.post("/admin/users/{user_id}/update-role")
async def admin_update_user_role(
    user_id: int,
    role: UserRole = Form(...),
    is_active: Optional[bool] = Form(None),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Update user role and active status"""
    from .admin_services import UserManagementService
    from .response_helpers import FormResponseHelper

    user_service = UserManagementService(session)

    try:
        # Update user using service with safety checks
        updated_user = await user_service.update_user_role(
            user_id, role, is_active, current_user
        )

        # Return success response using helper
        return FormResponseHelper.form_success(
            message=_("User updated successfully"),
            user={
                "id": updated_user.id,
                "email": updated_user.email,
                "full_name": updated_user.full_name,
                "role": updated_user.role.value,
                "is_active": updated_user.is_active,
            },
        )
    except Exception as exc:
        logger.error(f"Failed to update user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update user")


@app.get("/admin/logout")
async def admin_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
