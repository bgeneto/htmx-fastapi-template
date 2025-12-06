from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from ..auth import COOKIE_NAME
from ..auth_strategies import (
    AuthenticationRequest,
    OTPHandler,
    magic_link_strategy,
    otp_strategy,
)
from ..config import settings
from ..email import send_registration_notification
from ..i18n import gettext as _
from ..logger import get_logger
from ..models import User, UserRole
from ..repository import (
    create_user,
    get_session,
    get_user_by_email,
    get_valid_token,
    list_users,
    mark_token_used,
    verify_otp_code,
)
from ..response_helpers import FormResponseHelper
from ..schemas import LoginRequest, UserRegister
from ..templates import templates
from ..url_validator import validate_admin_redirect
from ..users import auth_backend, current_user_optional, get_jwt_strategy

router = APIRouter()
logger = get_logger("auth")


@router.get("/auth/register", response_class=HTMLResponse)
async def register_form(request: Request):
    """Display user registration form (only available in classic login mode)"""
    return templates.TemplateResponse(
        "pages/auth/register.html",
        {
            "request": request,
            "error": None,
            "login_method": settings.LOGIN_METHOD,
        },
    )


@router.post("/auth/register")
async def register(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    """Handle user self-registration (only available in classic login mode)"""
    # Only allow registration in classic login mode
    if settings.LOGIN_METHOD != "classic":
        return FormResponseHelper.form_error(
            message=_(
                "User registration is not available. Please log in using the magic link or OTP method."
            )
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

    # Create user with default role
    try:
        user = await create_user(
            session, payload, role=UserRole(settings.DEFAULT_USER_ROLE)
        )
        logger.info(f"New user registered: {user.email} (role: {user.role})")

        # Send notification to admins if user is pending
        if user.role == UserRole.PENDING:
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
        else:
            return FormResponseHelper.form_success(
                message=_("Registration successful! You can now log in.")
            )
    except Exception as exc:
        logger.error(f"Failed to create user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create account")


@router.get("/auth/login", response_class=HTMLResponse)
async def login_form(
    request: Request,
    user: Optional[User] = Depends(current_user_optional),
):
    """Display login form based on configured login method"""
    if user:
        redirect_url = "/admin" if user.role == UserRole.ADMIN else "/"
        return RedirectResponse(url=redirect_url, status_code=303)

    return templates.TemplateResponse(
        "pages/auth/login.html",
        {
            "request": request,
            "error": None,
            "login_method": settings.LOGIN_METHOD,
        },
    )


async def classic_login(
    request: Request,
    email: str,
    password: str,
    next_url: Optional[str],
    session: AsyncSession,
):
    """Classic username/password login using fastapi-users"""
    try:
        # Use fastapi-users authentication backend
        user = await auth_backend.login(email, password)

        if not user:
            return FormResponseHelper.form_error(
                message=_("Invalid email or password"),
            )

        # Generate token
        strategy = get_jwt_strategy()
        token = await strategy.write_token(user)

        # Set redirect URL
        redirect_url = "/admin" if user.role == UserRole.ADMIN else "/"
        if next_url:
            redirect_url = validate_admin_redirect(next_url, redirect_url)

        response = RedirectResponse(url=redirect_url, status_code=303)
        response.set_cookie(
            key="session",
            value=token,
            max_age=settings.SESSION_EXPIRY_DAYS * 24 * 60 * 60,
            secure=not settings.debug,
            httponly=True,
            samesite="lax",
        )

        return response

    except Exception as e:
        logger.error(f"Classic login error: {e}")
        return FormResponseHelper.form_error(
            message=_("Login failed. Please check your credentials and try again."),
        )


@router.post("/auth/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: Optional[str] = Form(None),
    next: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Handle login based on configured login method"""
    # Validate email format
    try:
        if settings.LOGIN_METHOD == "classic":
            LoginRequest.model_validate({"email": email, "password": password})
        else:
            LoginRequest.model_validate({"email": email})
    except ValidationError as e:
        return FormResponseHelper.form_error(
            message=_("Login failed"),
            field_errors={str(error["loc"][-1]): error["msg"] for error in e.errors()},
        )

    # Select strategy based on configuration
    if settings.LOGIN_METHOD == "otp":
        strategy = otp_strategy
    elif settings.LOGIN_METHOD == "magic":
        strategy = magic_link_strategy
    elif settings.LOGIN_METHOD == "classic":
        # Use fastapi-users for classic login
        return await classic_login(request, email, password, next, session)
    else:
        # Default to magic link for backward compatibility
        strategy = magic_link_strategy

    # Use authentication strategy
    logger.info(
        f"Attempting login with method: {settings.LOGIN_METHOD} for email: {email}"
    )
    auth_request = AuthenticationRequest(email, session, next)
    response = await strategy.handle_login(auth_request)

    if response:
        logger.info(f"Authentication strategy returned response for {email}")
        return response.to_response()

    # Redirect to check email page (for magic link when no response returned)
    # Check if request wants JSON (from JavaScript) or HTML
    accept_header = request.headers.get("accept", "")
    if "application/json" in accept_header:
        # Return JSON for AJAX requests
        return JSONResponse(
            content={
                "success": True,
                "redirect": "check_email",
                "email": email,
                "message": _("Check your email for the login link"),
            }
        )

    # Return HTML template for direct form submissions
    return templates.TemplateResponse(
        "pages/auth/check_email.html",
        {
            "request": request,
            "email": email,
            "login_method": settings.LOGIN_METHOD,
            "otp_expiry_minutes": settings.OTP_EXPIRY_MINUTES,
            "magic_link_expiry_minutes": settings.MAGIC_LINK_EXPIRY_MINUTES,
        },
    )


@router.get("/auth/verify-otp", response_class=HTMLResponse)
async def verify_otp_form(request: Request, email: str):
    """Display OTP verification form"""
    return templates.TemplateResponse(
        "pages/auth/verify_otp.html",
        {
            "request": request,
            "email": email,
            "error": None,
            "otp_expiry_minutes": settings.OTP_EXPIRY_MINUTES,
        },
    )


@router.get("/auth/check-email", response_class=HTMLResponse)
async def check_email_form(request: Request, email: str = ""):
    """Display check email page for magic link/OTP confirmation"""
    return templates.TemplateResponse(
        "pages/auth/check_email.html",
        {
            "request": request,
            "email": email,
            "login_method": settings.LOGIN_METHOD,
            "otp_expiry_minutes": settings.OTP_EXPIRY_MINUTES,
            "magic_link_expiry_minutes": settings.MAGIC_LINK_EXPIRY_MINUTES,
        },
    )


@router.post("/auth/verify-otp")
async def verify_otp(
    request: Request,
    email: str = Form(...),
    otp_code: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    """Verify OTP code and login user"""
    # Verify OTP code
    is_valid = await verify_otp_code(session, email, otp_code)

    if not is_valid:
        return templates.TemplateResponse(
            "pages/auth/verify_otp.html",
            {
                "request": request,
                "email": email,
                "error": _("Invalid or expired verification code. Please try again."),
                "otp_expiry_minutes": settings.OTP_EXPIRY_MINUTES,
            },
        )

    # Get user and create session
    user = await get_user_by_email(session, email)
    if not user or not user.is_active:
        return templates.TemplateResponse(
            "pages/auth/verify_otp.html",
            {
                "request": request,
                "email": email,
                "error": _("User not found or inactive. Please contact support."),
                "otp_expiry_minutes": settings.OTP_EXPIRY_MINUTES,
            },
        )

    # Check if user is pending approval
    if user.role == UserRole.PENDING:
        # Mark email as verified even for pending users (they verified OTP)
        if not user.email_verified:
            user.email_verified = True
            await session.commit()

        # Check if request wants JSON (from JavaScript)
        accept_header = request.headers.get("accept", "")
        if "application/json" in accept_header:
            # Return JSON redirect for AJAX requests
            return JSONResponse(
                content={
                    "success": True,
                    "redirect": f"/auth/pending-approval?email={email}",
                }
            )

        # Return HTML template for direct access
        return templates.TemplateResponse(
            "pages/auth/pending_approval.html",
            {
                "request": request,
                "email": email,
            },
        )

    # Mark email as verified for active users
    if not user.email_verified:
        user.email_verified = True
        await session.commit()

    # Generate JWT token using fastapi-users strategy
    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)

    # Redirect based on role
    redirect_url = "/admin" if user.role == UserRole.ADMIN else "/"

    response = RedirectResponse(url=redirect_url, status_code=303)

    # Set session cookie
    response.set_cookie(
        key="session",
        value=token,
        max_age=settings.SESSION_EXPIRY_DAYS * 24 * 60 * 60,
        secure=not settings.debug,
        httponly=True,
        samesite="lax",
    )

    return response


@router.get("/auth/pending-approval", response_class=HTMLResponse)
async def pending_approval_page(request: Request, email: str):
    """Display pending approval page for users awaiting admin approval"""
    return templates.TemplateResponse(
        "pages/auth/pending_approval.html",
        {
            "request": request,
            "email": email,
        },
    )


@router.post("/auth/resend-otp")
async def resend_otp(
    request: Request,
    email: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    """Resend OTP code"""
    # Get user
    user = await get_user_by_email(session, email)
    if not user or not user.is_active:
        # Don't reveal if user exists or not
        return JSONResponse(
            content={"success": True, "message": _("OTP sent successfully")},
            status_code=200,
        )

    # Send OTP
    otp_handler = OTPHandler()
    auth_request = AuthenticationRequest(email, session)
    await otp_handler.authenticate(auth_request)

    return JSONResponse(
        content={"success": True, "message": _("OTP sent successfully")},
        status_code=200,
    )


@router.get("/auth/verify/{token}")
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
    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)

    # Redirect based on role or next URL
    redirect_url = "/admin" if user.role == UserRole.ADMIN else "/"

    # Check for next URL in cookie or query param
    next_url = request.cookies.get("next_url") or request.query_params.get("next")

    if next_url:
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


@router.get("/auth/logout")
async def logout():
    """Log out current user"""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
