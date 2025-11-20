from contextlib import asynccontextmanager
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
    send_magic_link,
    send_registration_notification,
)
from .i18n import get_locale, get_translations, set_locale
from .i18n import gettext as _
from .logger import get_logger
from .models import Contact, User, UserRole
from .repository import (
    approve_user,
    create_contact,
    create_login_token,
    create_user,
    get_recent_contacts,
    get_session,
    get_user_by_email,
    get_valid_token,
    hash_password,
    list_contacts,
    list_users,
    mark_token_used,
    update_user,
    verify_password,
)
from .schemas import (
    AdminCreateUser,
    ContactCreate,
    LoginRequest,
    UserRegister,
    UserUpdate,
)

logger = get_logger("main")


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await init_db()
        logger.info("DB initialized on startup")
    except Exception as e:
        logger.error("DB init failed: {}", e)
    yield
    # Shutdown (if needed in the future)


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

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
        # Try to get locale from cookie first
        locale = request.cookies.get("locale")

        # Fall back to Accept-Language header
        if not locale:
            accept_language = request.headers.get("Accept-Language", "en")
            # Parse Accept-Language header (simple parsing)
            locale = accept_language.split(",")[0].split(";")[0].strip()
            # Normalize locale (e.g., en-US -> en, pt-BR -> pt_BR)
            if "-" in locale:
                parts = locale.split("-")
                if len(parts[1]) == 2 and parts[1].isupper():
                    # Country code: pt-BR -> pt_BR
                    locale = f"{parts[0]}_{parts[1]}"
                else:
                    # Language only: en-US -> en
                    locale = parts[0]

        # Set locale for this request
        set_locale(locale)

        # Make locale available in request state
        request.state.locale = locale

        response = await call_next(request)
        return response


app.add_middleware(LocaleMiddleware)


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
        # Translate Pydantic validation errors to user's language
        from .i18n import gettext as _

        errors = {}
        for err in e.errors():
            field = err["loc"][-1]
            msg = err["msg"]

            # Translate common Pydantic error messages
            if "String should have at least" in msg:
                if field == "name":
                    errors[field] = _("Name must be at least 2 characters")
                elif field == "message":
                    errors[field] = _("Message must be at least 5 characters")
            elif "value is not a valid email address" in msg.lower():
                errors[field] = _("Please enter a valid email address")
            elif "Field required" in msg:
                if field == "name":
                    errors[field] = _("Name is required")
                elif field == "email":
                    errors[field] = _("Email is required")
                elif field == "message":
                    errors[field] = _("Message is required")
            else:
                # Use the message from validator if it's already translated
                errors[field] = msg

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
        errors = {}
        for err in e.errors():
            field = err["loc"][-1]
            msg = err["msg"]
            if "String should have at least" in msg:
                errors[field] = _("Name must be at least 2 characters")
            elif "value is not a valid email address" in msg.lower():
                errors[field] = _("Please enter a valid email address")
            elif "Field required" in msg:
                errors[field] = _("This field is required")
            else:
                errors[field] = msg

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
        errors = {}
        for err in e.errors():
            field = err["loc"][-1]
            errors[field] = _("Please enter a valid email address")

        return JSONResponse(
            status_code=400, content={"errors": errors, "form": form_data}
        )

    # Get user
    user = await get_user_by_email(session, email)

    # Always return success to prevent email enumeration
    # But only send email if user exists and is active
    if user and user.is_active:
        # Check if user is pending
        if user.role == UserRole.PENDING:
            return JSONResponse(
                content={
                    "success": True,
                    "message": _("Your account is pending admin approval."),
                }
            )

        # Generate magic link token
        raw_token = await create_login_token(session, user)
        magic_link = f"{settings.APP_BASE_URL}/auth/verify/{raw_token}"

        # Send magic link email
        await send_magic_link(user.email, user.full_name, magic_link)
        logger.info(f"Magic link sent to {user.email}")
    else:
        logger.warning(f"Login attempt for non-existent/inactive user: {email}")

    # Always show check email page
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
    return templates.TemplateResponse(
        "pages/admin/login.html", {"request": request, "error": None}
    )


@app.post("/admin/login", response_class=HTMLResponse)
async def admin_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    """Bootstrap admin login with password (admin only)"""
    # Get user by email
    user = await get_user_by_email(session, email)

    # Verify user exists, has password, and is admin
    if not user or not user.hashed_password or user.role != UserRole.ADMIN:
        return templates.TemplateResponse(
            "pages/admin/login.html",
            {"request": request, "error": _("Invalid credentials")},
        )

    # Verify password
    if not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "pages/admin/login.html",
            {"request": request, "error": _("Invalid credentials")},
        )

    # Check if user is active
    if not user.is_active:
        return templates.TemplateResponse(
            "pages/admin/login.html",
            {"request": request, "error": _("Account is disabled")},
        )

    # Create session cookie
    assert user.id is not None  # User should exist from get_user_by_email
    cookie = create_session_cookie(user.id, user.email, user.role)
    response = RedirectResponse(url="/admin", status_code=303)
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
        errors = {}
        for err in e.errors():
            field = err["loc"][-1]
            msg = err["msg"]
            if "at least" in msg.lower():
                if field == "full_name":
                    errors[field] = _("Name must be at least 2 characters")
                elif field == "password":
                    errors[field] = _("Password must be at least 8 characters")
            else:
                errors[field] = msg

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
