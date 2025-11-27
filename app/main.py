from contextlib import asynccontextmanager
from datetime import datetime
from ipaddress import ip_address
from json import JSONEncoder
from typing import Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates  # type: ignore[import]
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

# Keep legacy auth for magic links
from .config import settings
from .db import init_db
from .i18n import get_locale, get_translations, set_locale
from .logger import get_logger
from .models import (
    User,
)
from .repository import (
    seed_cars,
)
from .routers import (
    admin,
    analytics,
    auth,
    books,
    cars,
    contacts,
    pages,
    users,
)
from .schemas import (
    UserCreate,
    UserRead,
    UserUpdate,
)
from .template_context import get_footer_context

# Import fastapi-users components
from .users import (
    auth_backend,
    current_user_optional,
    fastapi_users,
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
        # Initialize Resend API for email sending
        import resend

        if settings.EMAIL_API_KEY:
            resend.api_key = settings.EMAIL_API_KEY.get_secret_value()
            logger.info("Resend API initialized with key: {}...", resend.api_key[:10])
        else:
            logger.warning("EMAIL_API_KEY not configured - email sending will fail")

        await init_db()
        logger.info("DB initialized on startup")

        # Seed cars and books if needed
        from .db import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await seed_cars(session, count=500)
            from .repository import seed_books

            await seed_books(session, count=100)
    except Exception as exc:
        logger.error("Startup failed: {}", exc)
        raise
    yield
    # Shutdown (if needed in the future)


class DateTimeJSONEncoder(JSONEncoder):
    """Custom JSON encoder for datetime objects"""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Global dependency to inject user into request state and footer context
async def inject_context_variables_to_request_state(
    request: Request, user: Optional[User] = Depends(current_user_optional)
):
    request.state.user = user
    # Inject footer context variables (version, environment, current_year)
    footer_context = get_footer_context()
    for key, value in footer_context.items():
        setattr(request.state, key, value)


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
    json_encoders={datetime: lambda v: v.isoformat()},
    dependencies=[Depends(inject_context_variables_to_request_state)],
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
# fastapi-users provides: /auth/login (JWT), /auth/logout, /auth/register (if classic login)
# We also keep our custom routes for magic link and admin login
# The register router is only included if LOGIN_METHOD is set to 'classic'
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/api/auth",
    tags=["auth"],
)
# Only include register router if using classic login method
if settings.LOGIN_METHOD == "classic":
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/api/auth",
        tags=["auth"],
    )
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/api/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/api/users",
    tags=["users"],
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


# Include application routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(cars.router)
app.include_router(books.router)
app.include_router(contacts.router)
app.include_router(analytics.router)
app.include_router(pages.router)
