from contextlib import asynccontextmanager
from datetime import datetime
from json import JSONEncoder
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates  # type: ignore[import]
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from . import repository
from .auth import (
    COOKIE_NAME,
    create_session_cookie,
    require_admin,
)
from .config import settings
from .db import init_db
from .email import (
    send_account_approved,
    send_registration_notification,
)
from .grid_engine import GridEngine, PaginatedResponse
from .i18n import get_locale, get_translations, set_locale
from .i18n import gettext as _
from .logger import get_logger
from .models import Car, Contact, User, UserRole
from .repository import (
    approve_user,
    create_contact,
    create_user,
    get_recent_contacts,
    get_session,
    get_user_by_email,
    get_valid_token,
    hash_password,
    list_contacts,
    list_users,
    mark_token_used,
    seed_cars,
    update_user,
)
from .schemas import (
    AdminCreateUser,
    ContactCreate,
    LoginRequest,
    UserRegister,
    UserUpdate,
)
from .strategies import create_admin_login_verifier, handle_validation_error

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


class NextUrlMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle "next URL" redirects for authenticated pages.

    This middleware intercepts requests to admin routes that require authentication.
    If the user is not authenticated, it redirects them to the login page with
    the original URL stored as a "next" parameter for post-login redirect.
    """

    # Registry of admin routes that don't require authentication
    PUBLIC_ADMIN_ROUTES = ["/admin/cars"]

    async def dispatch(self, request: Request, call_next):
        # Check if this is an admin route that might require authentication
        if (
            request.url.path.startswith("/admin/")
            and request.url.path != "/admin/login"
            and request.url.path not in self.PUBLIC_ADMIN_ROUTES
        ):
            # Quick check for session cookie - if no cookie, redirect to login
            session_cookie = request.cookies.get(COOKIE_NAME)
            if not session_cookie:
                # No session cookie - redirect to login with next URL
                from urllib.parse import quote

                next_url = quote(str(request.url), safe="")
                login_url = f"/admin/login?next={next_url}"
                return RedirectResponse(url=login_url, status_code=302)

        # Continue processing the request
        response = await call_next(request)
        return response


app.add_middleware(NextUrlMiddleware)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """
    Custom exception handler for HTTP exceptions.

    Admin authentication redirects are now handled by NextUrlMiddleware.
    This handler provides JSON responses for API requests and HTML error pages for browsers.
    """
    # For all cases, use default JSON error handling
    # Admin HTML redirects are handled by NextUrlMiddleware before exceptions occur
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
        errors = handle_validation_error(e)

        # Return JSON for Alpine.js
        return JSONResponse(
            status_code=400, content={"errors": errors, "form": form_data}
        )

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
    form_data = {"email": email, "full_name": full_name}

    # Check if user already exists
    existing_user = await get_user_by_email(session, email)
    if existing_user:
        return JSONResponse(
            status_code=400,
            content={
                "errors": {"email": _("An account with this email already exists")},
                "form": form_data,
            },
        )

    # Validate with Pydantic
    try:
        payload = UserRegister.model_validate(form_data)
    except ValidationError as e:
        errors = handle_validation_error(e)
        return JSONResponse(
            status_code=400, content={"errors": errors, "form": form_data}
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

        return JSONResponse(
            content={
                "success": True,
                "message": _(
                    "Registration successful! Your account is pending admin approval."
                ),
            }
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
    session: AsyncSession = Depends(get_session),
):
    """Request magic link for passwordless login"""
    form_data = {"email": email}

    # Validate email format
    try:
        LoginRequest.model_validate(form_data)
    except ValidationError as e:
        errors = handle_validation_error(e)
        return JSONResponse(
            status_code=400, content={"errors": errors, "form": form_data}
        )

    from .auth_strategies import (
        AuthenticationRequest,
        default_auth_strategy,
    )

    # Use authentication strategy
    auth_request = AuthenticationRequest(email, session)
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

    # Redirect based on role
    redirect_url = "/admin" if user.role == UserRole.ADMIN else "/"
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
        except:
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
    form_data = {"email": email, "password": password}

    # Get user by email
    user = await get_user_by_email(session, email)

    # Check if user exists
    if not user:
        return JSONResponse(
            status_code=400,
            content={
                "errors": {"email": _("Invalid credentials")},
                "form": form_data,
            },
        )

    # Verify with strategy
    verifier = create_admin_login_verifier(user)
    if not verifier.verify(password=password):
        return JSONResponse(
            status_code=400,
            content={
                "errors": {"email": _("Invalid credentials")},
                "form": form_data,
            },
        )

    # Create session cookie - user exists and has ID at this point
    assert user.id is not None, "User must have an ID"
    cookie = create_session_cookie(user.id, user.email, user.role)

    # Determine redirect URL - use 'next' if provided and valid, otherwise default to /admin
    redirect_url = "/admin"
    if next:
        from urllib.parse import unquote, urlparse

        try:
            decoded_next = unquote(next)
            # Parse the URL to check its path
            parsed_url = urlparse(decoded_next)

            # Security validation: prevent redirects to sensitive endpoints
            sensitive_endpoints = [
                "/admin/logout",  # Don't auto-logout user after login
                "/admin/login",  # Don't redirect back to login
                "/auth/logout",  # Don't redirect to auth logout
                "/auth/login",  # Don't redirect to general login
            ]

            # Check if the path is safe:
            # 1. Must be relative (not external domain)
            # 2. Must not be in sensitive endpoints
            # 3. Must start with /admin to stay within admin area
            if (
                parsed_url.scheme == ""
                and parsed_url.netloc == ""
                and parsed_url.path.startswith("/admin")
                and parsed_url.path not in sensitive_endpoints
            ):
                redirect_url = decoded_next

        except Exception:
            # If decoding or validation fails, use default
            pass

    # Return success response - JavaScript will handle redirect
    response = JSONResponse(content={"success": True, "redirect_url": redirect_url})

    # Set session cookie on the response
    response.set_cookie(
        COOKIE_NAME, cookie, httponly=True, samesite="lax", secure=not settings.debug
    )

    logger.info(f"Bootstrap admin logged in: {user.email}")
    return response


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
    # current_user: User = Depends(require_admin),  # Commented out for public access
    session: AsyncSession = Depends(get_session),
):
    """Admin page for cars inventory - publicly accessible"""
    return templates.TemplateResponse(
        "pages/admin/cars.html",
        {
            "request": request,
            # "current_user": current_user,  # Not passed to template since public
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
    """API endpoint for cars grid (admin only)"""
    grid = GridEngine(session, Car)
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["make", "model"],
    )


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
    user = await repository.get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role != UserRole.PENDING:
        return JSONResponse(
            status_code=400, content={"error": _("User is not pending approval")}
        )

    # Approve user
    user = await approve_user(session, user, role)

    # Send approval notification
    login_url = f"{settings.APP_BASE_URL}/auth/login"
    await send_account_approved(user.email, user.full_name, login_url)

    logger.info(f"User {user.email} approved by {current_user.email}")

    return JSONResponse(
        content={
            "success": True,
            "message": _("User approved successfully"),
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "is_active": user.is_active,
                "email_verified": user.email_verified,
            },
        }
    )


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
    form_data = {
        "email": email,
        "full_name": full_name,
        "role": role,
        "password": password,
    }

    # Check if user exists
    existing_user = await get_user_by_email(session, email)
    if existing_user:
        return JSONResponse(
            status_code=400,
            content={
                "errors": {"email": _("User with this email already exists")},
                "form": form_data,
            },
        )

    # Validate
    try:
        payload = AdminCreateUser.model_validate(form_data)
    except ValidationError as e:
        errors = handle_validation_error(e)
        return JSONResponse(
            status_code=400, content={"errors": errors, "form": form_data}
        )

    # Hash password if provided
    hashed_password = hash_password(password) if password else None

    # Create user
    try:
        user = await create_user(
            session, payload, role=payload.role, hashed_password=hashed_password
        )

        # Mark as verified since admin created it
        user.email_verified = True
        await session.commit()

        logger.info(f"Admin {current_user.email} created user {user.email}")

        return JSONResponse(
            content={
                "success": True,
                "message": _("User created successfully"),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "is_active": user.is_active,
                },
            }
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
    user = await repository.get_user_by_id(session, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deactivating themselves
    if user.id == current_user.id and is_active is False:
        return JSONResponse(
            status_code=400,
            content={"error": _("You cannot deactivate your own account")},
        )

    # Update user
    update_data = UserUpdate(role=role, is_active=is_active, full_name=None)
    updated_user = await update_user(session, user, update_data)

    logger.info(f"Admin {current_user.email} updated user {updated_user.email}")

    return JSONResponse(
        content={
            "success": True,
            "message": _("User updated successfully"),
            "user": {
                "id": updated_user.id,
                "email": updated_user.email,
                "full_name": updated_user.full_name,
                "role": updated_user.role.value,
                "is_active": updated_user.is_active,
            },
        }
    )


@app.get("/admin/logout")
async def admin_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
