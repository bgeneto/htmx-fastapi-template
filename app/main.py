import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from ipaddress import ip_address
from json import JSONEncoder
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates  # type: ignore[import]
from pydantic import ValidationError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

# Keep legacy auth for magic links
from .auth import (
    COOKIE_NAME,
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
    PasswordChange,
    UserCreate,
    UserRead,
    UserRegister,
    UserUpdate,
)

# Import fastapi-users components
from .users import (
    auth_backend,
    current_active_user,
    current_user_optional,
    fastapi_users,
    password_helper,
    require_admin,
)

logger = get_logger("main")


def get_allowed_hosts() -> list[str]:
    """
    Extract allowed hosts from APP_BASE_URL for TrustedHostMiddleware.

    Returns a list containing the domain and common variations.
    """
    logger.debug("Getting allowed hosts from APP_BASE_URL={}", settings.APP_BASE_URL)

    parsed = urlparse(settings.APP_BASE_URL)
    logger.debug(
        "Parsed APP_BASE_URL: scheme={}, hostname={}, path={}",
        parsed.scheme,
        parsed.hostname,
        parsed.path,
    )

    hosts = []

    # Add the main hostname
    if parsed.hostname:
        hosts.append(parsed.hostname)
        logger.debug("Added main hostname: {}", parsed.hostname)

        # Add wildcard subdomain variant only for real domains (not localhost or IPs)
        is_ip = False
        try:
            # Try to parse as IP address
            ip_address(parsed.hostname)
            is_ip = True
            logger.debug("Hostname {} is detected as IP address", parsed.hostname)
        except ValueError:
            # Not an IP address
            logger.debug("Hostname {} is detected as domain name", parsed.hostname)

        if not (parsed.hostname.startswith("localhost") or is_ip):
            wildcard_host = f"*.{parsed.hostname}"
            hosts.append(wildcard_host)
            logger.debug("Added wildcard subdomain: {}", wildcard_host)
        else:
            logger.debug(
                "Skipping wildcard subdomain for localhost or IP: {}", parsed.hostname
            )

    # Always allow localhost for development (use set to avoid duplicates)
    localhost_hosts = {"localhost", "localhost:8000", "127.0.0.1", "127.0.0.1:8000"}
    for host in localhost_hosts:
        if host not in hosts:
            hosts.append(host)
            logger.debug("Added localhost host: {}", host)

    logger.info("Final allowed hosts for TrustedHostMiddleware: {}", hosts)
    return hosts


def get_cors_origins() -> list[str]:
    """
    Get allowed CORS origins from APP_BASE_URL.

    Returns a list containing the full URL.
    """
    origins = [settings.APP_BASE_URL]

    # Allow localhost for development
    if not settings.APP_BASE_URL.startswith("http://localhost"):
        origins.extend(
            [
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ]
        )

    return origins


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await init_db()
        logger.info("DB initialized on startup")

        # Seed cars and books if needed
        from .db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await seed_cars(session, count=500)
            from .repository import seed_books

            await seed_books(session, count=100)

        # Start background email worker
        from .email_worker import email_worker
        import asyncio

        # Start email worker in background
        asyncio.create_task(email_worker.start())
        logger.info("Email worker started")

    except Exception as exc:
        logger.error("Startup failed: {}", exc)
        raise

    yield

    # Shutdown
    try:
        # Stop email worker
        from .email_worker import email_worker
        await email_worker.stop()
        logger.info("Email worker stopped")

        # Close Redis connections
        from .redis_utils import close_redis
        await close_redis()
        logger.info("Redis connections closed")

    except Exception as exc:
        logger.error("Shutdown error: {}", exc)


class DateTimeJSONEncoder(JSONEncoder):
    """Custom JSON encoder for datetime objects"""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Global dependency to inject user into request state
async def inject_user_to_request_state(
    request: Request, user: Optional[User] = Depends(current_user_optional)
):
    request.state.user = user


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
    json_encoders={datetime: lambda v: v.isoformat()},
    dependencies=[Depends(inject_user_to_request_state)],
)


# Middleware for host header logging (diagnostic)
class HostHeaderLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        host_header = request.headers.get("host", "NOT_SET")
        forwarded_host = request.headers.get("x-forwarded-host", "NOT_SET")
        logger.debug(
            "Incoming request Host header: '{}' | X-Forwarded-Host: '{}' | URL: {} {}",
            host_header,
            forwarded_host,
            request.method,
            request.url.path,
        )
        return await call_next(request)


# app.add_middleware(HostHeaderLoggingMiddleware) # debug only

# Security Middleware Configuration
# TrustedHostMiddleware - validates Host header to prevent host header injection attacks
# allowed_hosts = get_allowed_hosts()
# logger.debug("Configuring TrustedHostMiddleware with allowed_hosts: {}", allowed_hosts)
# app.add_middleware(
#    TrustedHostMiddleware,
#    allowed_hosts=allowed_hosts,
# )


# Add middleware
# CORSMiddleware - controls which origins can make cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# NOTE: GZipMiddleware is explicitly disabled because we're using a reverse proxy
# (like Nginx or Caddy) that handles compression more efficiently.
# If you're not using a reverse proxy, you can uncomment the line below:
# app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include fastapi-users routers for auth
# NOTE: We keep our custom magic link authentication alongside fastapi-users
# fastapi-users provides: /auth/login (JWT), /auth/logout, /auth/register
# We also keep our custom routes for magic link and admin login
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/api/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/api/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/api/users",
    tags=["users"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/api/auth",
    tags=["auth"],
)

# Custom OTP endpoints that use our Resend integration
from .otp_config import request_otp_with_resend, verify_otp_with_resend

@app.post("/auth/otp/request")
async def custom_otp_request(request: Request):
    """Custom OTP request endpoint that uses Resend instead of SMTP"""
    form = await request.form()
    email = form.get("email", "").strip().lower()

    if not email:
        return JSONResponse(
            status_code=400,
            content={"detail": "Email is required"}
        )

    # Apply rate limiting
    from .redis_utils import auth_rate_limiter
    rate_result = await auth_rate_limiter.is_allowed(
        identifier=f"otp_request:{request.client.host}",
        limit=5,  # 5 requests per window
        window=300  # 5 minute window
    )

    if not rate_result["allowed"]:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many OTP requests. Please try again later."}
        )

    result = await request_otp_with_resend(email)

    if result["status"] == "success":
        return JSONResponse(
            status_code=200,
            content={"detail": "OTP code sent successfully"}
        )
    else:
        return JSONResponse(
            status_code=500,
            content={"detail": result["message"]}
        )

@app.post("/auth/otp/verify")
async def custom_otp_verify(request: Request):
    """Custom OTP verification endpoint that works with Resend-sent codes"""
    form = await request.form()
    email = form.get("email", "").strip().lower()
    otp_code = form.get("otp_code", "").strip()

    if not email or not otp_code:
        return JSONResponse(
            status_code=400,
            content={"detail": "Email and OTP code are required"}
        )

    # Apply rate limiting
    from .redis_utils import auth_rate_limiter
    rate_result = await auth_rate_limiter.is_allowed(
        identifier=f"otp_verify:{request.client.host}",
        limit=10,  # 10 attempts per window
        window=300  # 5 minute window
    )

    if not rate_result["allowed"]:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many verification attempts. Please try again later."}
        )

    result = await verify_otp_with_resend(email, otp_code)

    if result["status"] == "success":
        # Set JWT token in cookie compatible with fastapi-users
        response = JSONResponse(
            status_code=200,
            content={
                "detail": "Login successful",
                "access_token": result["access_token"],
                "token_type": result["token_type"]
            }
        )

        from .config import settings
        response.set_cookie(
            key="fastapiusersauth",
            value=f"{result['token_type']} {result['access_token']}",
            max_age=settings.SESSION_EXPIRY_DAYS * 24 * 60 * 60,
            secure=settings.COOKIE_SECURE,
            httponly=True,
            samesite="lax"
        )
        return response
    else:
        return JSONResponse(
            status_code=400,
            content={"detail": result["message"]}
        )

# Include OTP authentication router (for refresh tokens and other functionality)
from .otp_config import otp_router

app.include_router(
    otp_router,
    prefix="/auth/otp",
    tags=["auth"],
)

# Add OTP verification route to handle redirect from login
@app.get("/auth/otp/verify", response_class=HTMLResponse)
async def otp_verify_form(request: Request):
    """Display OTP verification form"""
    # Get email from query parameters
    email = request.query_params.get("email", "")
    next_url = request.query_params.get("next", "")

    return templates.TemplateResponse(
        "pages/auth/verify_otp.html",
        {
            "request": request,
            "email": email,
            "next": next_url
        }
    )

templates = Jinja2Templates(directory="templates")

# Configure Jinja2 with i18n extension
templates.env.add_extension("jinja2.ext.i18n")
templates.env.install_gettext_callables(  # type: ignore[attr-defined]
    gettext=lambda x: get_translations(get_locale()).gettext(x),
    ngettext=lambda s, p, n: get_translations(get_locale()).ngettext(s, p, n),
    newstyle=True,
)


# Global template context for all templates
def get_template_context():
    """Get global context for all templates with caching."""
    # This data changes rarely, so we can use module-level caching
    if not hasattr(get_template_context, '_cached_context'):
        get_template_context._cached_context = {
            "enable_i18n": settings.ENABLE_I18N,
            "settings": {
                "LOGIN_METHOD": settings.LOGIN_METHOD,
                "OTP_EXPIRY_MINUTES": settings.OTP_EXPIRY_MINUTES,
                "MAGIC_LINK_EXPIRY_MINUTES": settings.MAGIC_LINK_EXPIRY_MINUTES,
            }
        }
    return get_template_context._cached_context


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
    # Check if it's an API request
    is_api_request = request.url.path.startswith("/api/")

    if exc.status_code == 401:
        if is_api_request:
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )

        # For HTML requests, redirect to appropriate login page
        # For HTML requests, redirect to appropriate login page
        response_url = (
            "/admin/login" if request.url.path.startswith("/admin") else "/auth/login"
        )
        response = RedirectResponse(url=response_url, status_code=302)

        # Set next URL in cookie for post-login redirect
        # We use a separate cookie to avoid URL parameter pollution and open redirect issues
        # Store only relative path + query to pass strict URL validation
        next_path = request.url.path
        if request.url.query:
            next_path += f"?{request.url.query}"

        response.set_cookie(
            "next_url",
            next_path,
            httponly=True,
            samesite="lax",
            secure=not settings.debug,
            max_age=300,  # 5 minutes expiry
        )
        return response

    elif exc.status_code == 403:
        # Forbidden - show nice error page for HTML requests
        if is_api_request:
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        return templates.TemplateResponse(
            "errors/403.html", {"request": request}, status_code=403
        )

    elif exc.status_code == 404:
        # Not Found - show nice error page for HTML requests
        if is_api_request:
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        return templates.TemplateResponse(
            "errors/404.html", {"request": request}, status_code=404
        )

    elif exc.status_code == 500:
        # Internal Server Error - show nice error page for HTML requests
        if is_api_request:
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
        return templates.TemplateResponse(
            "errors/500.html", {"request": request}, status_code=500
        )

    # For other unknown errors
    if is_api_request:
        # API requests get JSON response
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    else:
        # HTML requests get a friendly error page with translation support
        return templates.TemplateResponse(
            "errors/5xx.html",
            {"request": request, "error_code": exc.status_code},
            status_code=exc.status_code,
        )


# Handle 404 errors for non-existent routes
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors with custom template for HTML requests."""
    # Check if it's an API request
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return templates.TemplateResponse(
        "errors/404.html", {"request": request}, status_code=404
    )


# Handle 500 errors for unhandled exceptions
@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors with custom template for HTML requests."""
    logger.error(f"Internal server error: {exc}")

    # Check if it's an API request
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )
    return templates.TemplateResponse(
        "errors/500.html", {"request": request}, status_code=500
    )


# Handle all other unhandled exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    # Check if it's an API request
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )
    return templates.TemplateResponse(
        "errors/500.html", {"request": request}, status_code=500
    )


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    user: Optional[User] = Depends(current_user_optional),
    session: AsyncSession = Depends(get_session),
):
    response = templates.TemplateResponse(
        "pages/index.html",
        {
            "request": request,
            "user": user,
        },
    )
    # Cache headers for improved performance
    response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
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
async def contacts_page(
    request: Request,
    user: Optional[User] = Depends(current_user_optional),
):
    """Display contacts directory page with data grid"""
    return templates.TemplateResponse(
        "pages/contacts.html",
        {
            "request": request,
            "user": user,
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
    # Create cache key from request parameters
    from .redis_utils import api_cache
    import hashlib
    import json

    # Generate cache key from query parameters
    query_params = dict(request.query_params)
    cache_key_data = {
        "endpoint": "contacts",
        "params": query_params,
        "page": page,
        "limit": limit,
        "sort": sort,
        "dir": dir
    }
    cache_key = f"contacts_grid:{hashlib.md5(json.dumps(cache_key_data, sort_keys=True).encode()).hexdigest()}"

    # Try to get from cache first
    cached_result = await api_cache.get(cache_key)
    if cached_result:
        return cached_result

    # If not in cache, execute the query
    grid = GridEngine(session, Contact)
    result = await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["name", "email"],
    )

    # Cache the result for 5 minutes (300 seconds)
    await api_cache.set(cache_key, result, ttl=300)

    return result


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
    # Create cache key from request parameters
    from .redis_utils import api_cache
    import hashlib
    import json

    # Generate cache key from query parameters
    query_params = dict(request.query_params)
    cache_key_data = {
        "endpoint": "admin_users",
        "params": query_params,
        "page": page,
        "limit": limit,
        "sort": sort,
        "dir": dir
    }
    cache_key = f"admin_users_grid:{hashlib.md5(json.dumps(cache_key_data, sort_keys=True).encode()).hexdigest()}"

    # Try to get from cache first
    cached_result = await api_cache.get(cache_key)
    if cached_result:
        return cached_result

    # If not in cache, execute the query
    grid = GridEngine(session, User)
    result = await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["email", "full_name"],
    )

    # Cache the result for 3 minutes (180 seconds) - user data changes more frequently
    await api_cache.set(cache_key, result, ttl=180)

    return result


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

    # Apply rate limiting
    from .redis_utils import auth_rate_limiter
    rate_result = await auth_rate_limiter.is_allowed(
        identifier=f"register:{request.client.host}",
        limit=3,  # 3 registrations per hour
        window=3600  # 1 hour window
    )

    if not rate_result["allowed"]:
        return FormResponseHelper.error_response(
            request=request,
            error_message=_("Too many registration attempts. Please try again later."),
            form_data={"email": email, "full_name": full_name}
        )

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
            field_errors={str(error["loc"][-1]): error["msg"] for error in e.errors()},
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

    # Apply rate limiting
    from .redis_utils import auth_rate_limiter
    rate_result = await auth_rate_limiter.is_allowed(
        identifier=f"login:{request.client.host}",
        limit=10,  # 10 login attempts per 5 minutes
        window=300  # 5 minute window
    )

    if not rate_result["allowed"]:
        return FormResponseHelper.error_response(
            request=request,
            error_message=_("Too many login attempts. Please try again later."),
            form_data={"email": email}
        )

    form_data = {"email": email}

    # Validate email format
    try:
        LoginRequest.model_validate(form_data)
    except ValidationError as e:
        return FormResponseHelper.form_error(
            message=_("Login failed"),
            field_errors={str(error["loc"][-1]): error["msg"] for error in e.errors()},
        )

    from .auth_strategies import (
        AuthenticationRequest,
        default_auth_strategy,
    )
    from .config import settings

    # Use authentication strategy
    auth_request = AuthenticationRequest(email, session, next)
    response = await default_auth_strategy.handle_login(auth_request)

    if response:
        return response.to_response()

    # Redirect to appropriate page based on login method
    if settings.LOGIN_METHOD.lower() == "otp":
        # For OTP, redirect to OTP verification page
        from urllib.parse import quote
        otp_verify_url = f"/auth/otp/verify?email={quote(email)}"
        if next:
            otp_verify_url += f"&next={quote(next)}"
        return RedirectResponse(url=otp_verify_url, status_code=302)
    else:
        # For magic link, redirect to check email page
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

    # Generate JWT token using fastapi-users strategy
    from .users import get_jwt_strategy

    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)

    # Redirect based on role or next URL
    redirect_url = "/admin" if user.role == UserRole.ADMIN else "/"

    # Check for next URL in cookie or query param
    next_url = request.cookies.get("next_url") or request.query_params.get("next")

    if next_url:
        from .url_validator import validate_admin_redirect

        # Validate redirect URL to prevent open redirects
        redirect_url = validate_admin_redirect(next_url, redirect_url)

    response = RedirectResponse(url=redirect_url, status_code=303)

    # Set session cookie (JWT)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
    )

    # Clear next_url cookie
    response.delete_cookie("next_url")

    logger.info(f"User logged in via magic link: {user.email}")
    return response


@app.get("/auth/logout")
async def logout():
    """Log out current user"""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ============= Profile Routes =============


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    user: User = Depends(current_active_user),
):
    """Display user profile page"""
    return templates.TemplateResponse(
        "pages/profile.html",
        {
            "request": request,
            "user": user,
        },
    )


@app.post("/api/profile/update")
async def update_profile(
    request: Request,
    full_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Update user profile information"""
    from .response_helpers import FormResponseHelper

    form_data = {"full_name": full_name, "email": email, "phone": phone}

    # Update user fields if provided
    if full_name is not None:
        form_data["full_name"] = full_name
        if len(full_name.strip()) < 2:
            return FormResponseHelper.form_error(
                message=_("Name must be at least 2 characters"),
            )
        user.full_name = full_name.strip()

    if email is not None:
        # Basic email validation
        if "@" not in email or "." not in email:
            return FormResponseHelper.form_error(
                message=_("Invalid email address"),
            )
        # Check if email is already taken by another user
        existing = await get_user_by_email(session, email)
        if existing and existing.id != user.id:
            return FormResponseHelper.form_error(
                message=_("Email already in use by another account"),
                form_data=form_data,
            )
        user.email = email

    if phone is not None:
        # Basic phone validation (optional, just trim whitespace)
        phone = phone.strip()
        if phone and len(phone) > 20:
            return FormResponseHelper.form_error(
                message=_("Phone number too long (max 20 characters)"),
            )
        user.phone = phone if phone else None

    # Handle profile picture upload
    if profile_picture and profile_picture.filename:
        # Validate file type
        allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp"]
        if profile_picture.content_type not in allowed_types:
            return FormResponseHelper.form_error(
                message=_("Invalid file type. Please upload PNG, JPG, or WebP image."),
            )

        # Validate file size (5MB max)
        content = await profile_picture.read()
        if len(content) > 5 * 1024 * 1024:
            return FormResponseHelper.form_error(
                message=_("File too large. Maximum size is 5MB."),
            )

        # Save file to disk
        upload_dir = Path("static/uploads/profile_pictures")
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        file_ext = Path(profile_picture.filename).suffix
        unique_filename = f"{user.id}_{uuid.uuid4().hex[:8]}{file_ext}"
        file_path = upload_dir / unique_filename

        # Delete old profile picture if exists
        if user.profile_picture:
            old_file_path = Path(f"static{user.profile_picture}")
            if old_file_path.exists():
                old_file_path.unlink()

        # Write new file
        with open(file_path, "wb") as f:
            f.write(content)

        # Store relative path in database (must match static file mount at /static)
        user.profile_picture = f"/static/uploads/profile_pictures/{unique_filename}"

    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info(f"Profile updated for user: {user.email}")

    # Return profile picture URL if updated
    response_data = {"success": True, "message": _("Profile updated successfully")}
    if user.profile_picture:
        response_data["profile_picture"] = user.profile_picture

    return JSONResponse(content=response_data)


@app.post("/api/profile/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Change user password"""
    from .response_helpers import FormResponseHelper

    form_data = {
        "current_password": current_password,
        "new_password": new_password,
        "confirm_password": confirm_password,
    }

    # Validate with Pydantic
    try:
        payload = PasswordChange.model_validate(form_data)
    except ValidationError as e:
        return FormResponseHelper.form_error(
            message=_("Password change failed"),
            field_errors={str(error["loc"][-1]): error["msg"] for error in e.errors()},
        )

    # Verify current password
    if not user.hashed_password:
        return FormResponseHelper.form_error(
            message=_("No password set for this account. Use magic link login."),
        )

    is_valid, updated_hash = password_helper.verify_and_update(
        payload.current_password, user.hashed_password
    )

    if not is_valid:
        return FormResponseHelper.form_error(
            message=_("Password change failed"),
            field_errors={"current_password": _("Current password is incorrect")},
        )

    # Hash and set new password
    user.hashed_password = password_helper.hash(payload.new_password)
    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()

    logger.info(f"Password changed for user: {user.email}")
    return FormResponseHelper.form_success(message=_("Password changed successfully"))


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
        # Check for next URL in cookie if not provided in params
        actual_next = next or request.cookies.get("next_url")

        # Authenticate user using service with guard clauses
        result = await login_service.authenticate(email, password, actual_next)

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

        # Clear next_url cookie if it exists
        response.delete_cookie("next_url")

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
    current_user: User = Depends(require_admin),
    session_db: AsyncSession = Depends(get_session),
):
    # show list of contacts
    contacts = await list_contacts(session_db, limit=100)
    return templates.TemplateResponse(
        "pages/admin/index.html",
        {"request": request, "contacts": contacts, "user": current_user},
    )


@app.post("/admin/contact/delete", response_class=HTMLResponse)
async def admin_delete_contact(
    request: Request,
    id: int = Form(...),
    session=Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    # simple delete operation
    await db.execute(__import__("sqlmodel").sql.delete(Contact).where(Contact.id == id))  # type: ignore[arg-type]
    await db.commit()
    return RedirectResponse(url="/admin", status_code=303)


# ============= Admin Cars Routes =============

async def invalidate_cars_cache():
    """Invalidate all cached car data grid results"""
    from .redis_utils import api_cache
    try:
        # Delete all cache keys matching the pattern for car grids
        deleted_count = await api_cache.delete_pattern("admin_cars_grid:*")
        if deleted_count > 0:
            from app.logger import logger
            logger.info(f"Invalidated {deleted_count} car grid cache entries")
    except Exception as e:
        from app.logger import logger
        logger.error(f"Error invalidating car cache: {e}")


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
            "user": current_user,
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
    # Create cache key from request parameters
    from .redis_utils import api_cache
    import hashlib
    import json

    # Generate cache key from query parameters
    query_params = dict(request.query_params)
    cache_key_data = {
        "endpoint": "admin_cars",
        "params": query_params,
        "page": page,
        "limit": limit,
        "sort": sort,
        "dir": dir
    }
    cache_key = f"admin_cars_grid:{hashlib.md5(json.dumps(cache_key_data, sort_keys=True).encode()).hexdigest()}"

    # Try to get from cache first
    cached_result = await api_cache.get(cache_key)
    if cached_result:
        # Ensure cached result is properly serialized to dict for FastAPI response
        if isinstance(cached_result, dict):
            return cached_result
        elif hasattr(cached_result, 'model_dump'):
            return cached_result.model_dump()
        elif hasattr(cached_result, 'dict'):
            return cached_result.dict()
        else:
            # Fallback: convert to dict manually
            return {
                "items": cached_result.items if hasattr(cached_result, 'items') else [],
                "total": cached_result.total if hasattr(cached_result, 'total') else 0,
                "page": cached_result.page if hasattr(cached_result, 'page') else page,
                "limit": cached_result.limit if hasattr(cached_result, 'limit') else limit,
                "total_pages": cached_result.total_pages if hasattr(cached_result, 'total_pages') else 0,
            }

    # If not in cache, execute the query
    grid = GridEngine(session, Car)
    result = await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["make", "model", "version", "year", "price"],
    )

    # Cache the result for 5 minutes (300 seconds)
    # Ensure proper serialization before caching
    cache_data = result.model_dump() if hasattr(result, 'model_dump') else result.dict() if hasattr(result, 'dict') else result
    await api_cache.set(cache_key, cache_data, ttl=300)

    return result


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

    # Invalidate cache since we created a new car
    await invalidate_cars_cache()

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

    # Invalidate cache since we updated a car
    await invalidate_cars_cache()

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

        await session.execute(delete(Car).where(Car.id == car_id))  # type: ignore[arg-type]
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

        # Invalidate cache since we deleted a car
        await invalidate_cars_cache()

        return {"success": True, "message": "Car deleted successfully"}

    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete car ID {car_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete car: {str(e)}")


# ============= Book Routes (Universal Grid Demo) =============


@app.get("/books", response_class=HTMLResponse)
async def books_page(
    request: Request,
    user: Optional[User] = Depends(current_user_optional),
):
    """Display books page with universal data grid"""
    return templates.TemplateResponse(
        "pages/books.html",
        {
            "request": request,
            "user": user,
            "api_url": "/api/books",
            # Note: We don't strictly need to pass columns here if the frontend
            # could also auto-detect, but for now we define frontend columns manually.
            # The backend GridEngine WILL auto-detect search fields.
            "columns": [
                {"key": "id", "label": _("ID"), "width": 70, "sortable": True},
                {
                    "key": "title",
                    "label": _("Title"),
                    "width": 250,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "author",
                    "label": _("Author"),
                    "width": 200,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "isbn",
                    "label": _("ISBN"),
                    "width": 150,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "published_year",
                    "label": _("Year"),
                    "width": 100,
                    "sortable": True,
                },
                {
                    "key": "price",
                    "label": _("Price"),
                    "width": 100,
                    "sortable": True,
                },
                {"key": "pages", "label": _("Pages"), "width": 100, "sortable": True},
                {
                    "key": "summary",
                    "label": _("Summary"),
                    "width": 300,
                    "sortable": False,
                },
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
    # Create cache key from request parameters
    from .redis_utils import api_cache
    import hashlib
    import json

    # Generate cache key from query parameters
    query_params = dict(request.query_params)
    cache_key_data = {
        "endpoint": "books",
        "params": query_params,
        "page": page,
        "limit": limit,
        "sort": sort,
        "dir": dir
    }
    cache_key = f"books_grid:{hashlib.md5(json.dumps(cache_key_data, sort_keys=True).encode()).hexdigest()}"

    # Try to get from cache first
    cached_result = await api_cache.get(cache_key)
    if cached_result:
        return cached_result

    # If not in cache, execute the query
    grid = GridEngine(session, Book)
    # Note: We do NOT pass search_fields here to test auto-detection!
    result = await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
    )

    # Cache the result for 5 minutes (300 seconds)
    await api_cache.set(cache_key, result, ttl=300)

    return result


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
        {"request": request, "users": users, "user": current_user},
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
