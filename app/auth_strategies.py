from typing import Optional, Protocol

from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from .i18n import gettext as _
from .logger import get_logger
from .models import UserRole

logger = get_logger(__name__)


class AuthenticationRequest:
    def __init__(self, email: str, session: AsyncSession, next_url: Optional[str] = None):
        self.email = email
        self.session = session
        self.next_url = next_url


class AuthenticationResponse(Protocol):
    def to_response(self) -> JSONResponse: ...


class SuccessResponse:
    def __init__(self, message: str):
        self.message = message

    def to_response(self) -> JSONResponse:
        return JSONResponse(content={"success": True, "message": self.message})


class OTPVerificationResponse:
    """Response for OTP verification indicating redirect to verification page"""
    def __init__(self, email: str):
        self.email = email

    def to_response(self) -> JSONResponse:
        return JSONResponse(content={
            "success": True,
            "redirect": "verify_otp",
            "email": self.email,
            "message": _("OTP sent successfully")
        })


class MagicLinkHandler:
    """Handles magic link login process."""

    async def authenticate(
        self, request: AuthenticationRequest
    ) -> Optional[AuthenticationResponse]:
        from .config import settings
        from .email import send_magic_link
        from .repository import (
            create_login_token,
            get_user_by_email,
        )

        # Get user
        user = await get_user_by_email(request.session, request.email)

        # Always return success to prevent email enumeration
        if user and user.is_active:
            # Check if user is pending
            if user.role == UserRole.PENDING:
                return SuccessResponse(_("Your account is pending admin approval."))

            # Generate magic link token
            raw_token = await create_login_token(request.session, user)
            magic_link = f"{settings.APP_BASE_URL}/auth/verify/{raw_token}"

            if request.next_url:
                from urllib.parse import quote
                magic_link += f"?next={quote(request.next_url)}"

            # Send magic link email
            await send_magic_link(user.email, user.full_name, magic_link)
        else:
            # Log warning for non-existent/inactive user (for monitoring)
            pass

        # Always show check email page
        return None  # Signal to redirect to check email page


class OTPHandler:
    """Handles OTP login process with auto-registration."""

    async def authenticate(
        self, request: AuthenticationRequest
    ) -> Optional[AuthenticationResponse]:
        from .email import send_otp_code
        from .repository import get_user_by_email

        # Get user
        user = await get_user_by_email(request.session, request.email)
        logger.info(f"OTPHandler: User lookup for {request.email}: user={'found' if user else 'NOT FOUND'}, is_active={user.is_active if user else 'N/A'}")

        # Auto-create user if not found
        if not user:
            try:
                from .config import settings
                from .models import User

                # Extract name from email (everything before @)
                email_username = request.email.split('@')[0]
                # Capitalize and replace dots/underscores with spaces
                auto_name = email_username.replace('.', ' ').replace('_', ' ').title()

                # Determine user role and status based on settings
                if settings.REQUIRE_ADMIN_APPROVAL:
                    user_role = UserRole.PENDING
                    is_active = True  # Active but with PENDING role (needs approval)
                    logger.info(f"OTPHandler: Auto-creating PENDING user for {request.email} (requires admin approval)")
                else:
                    user_role = UserRole.USER
                    is_active = True
                    logger.info(f"OTPHandler: Auto-creating active USER for {request.email} (instant access)")

                # Create user directly without password (passwordless OTP login)
                user = User(
                    email=request.email,
                    full_name=auto_name,
                    is_active=is_active,
                    role=user_role,
                    hashed_password=""  # No password for OTP users
                )

                # Add to session and commit
                request.session.add(user)
                await request.session.commit()
                logger.info(f"OTPHandler: Successfully created user for {request.email} with role={user_role}")

            except Exception as e:
                logger.error(f"OTPHandler: Failed to auto-create user for {request.email}: {e}")
                logger.exception("Full traceback:")
                # Still return success to prevent enumeration
                return OTPVerificationResponse(request.email)

        # Check if user is active
        if not user.is_active:
            logger.warning(f"OTPHandler: User INACTIVE for email {request.email} - skipping OTP send")
            # Still return success to prevent enumeration
            return OTPVerificationResponse(request.email)

        # Check if user is pending approval - do NOT send OTP
        if user.role == UserRole.PENDING:
            logger.info(f"OTPHandler: User PENDING for {request.email} - returning approval message")
            return SuccessResponse(_("Your account is pending admin approval. You will be notified once approved."))

        # Generate and send OTP code
        try:
            from .repository import create_otp_code
            logger.info(f"Creating OTP code for email: {request.email}")
            otp_code = await create_otp_code(request.session, request.email)
            logger.info(f"OTP code generated successfully: {otp_code[:2]}**** for {request.email}")

            # Send OTP email
            logger.info(f"Attempting to send OTP email to {request.email}")
            email_sent = await send_otp_code(request.email, user.full_name, otp_code)
            logger.info(f"OTP email sending result for {request.email}: {email_sent}")

            if not email_sent:
                logger.error(f"OTP email failed to send to {request.email} - email_sent returned False")

            # Return response indicating OTP verification page
            return OTPVerificationResponse(request.email)

        except Exception as e:
            # Log error but still show generic success to prevent enumeration
            logger.error(f"Error in OTP generation/sending for {request.email}: {e}")
            logger.exception("Full traceback:")
            # Still return success to prevent enumeration
            return OTPVerificationResponse(request.email)


class AuthenticationStrategy(Protocol):
    async def handle_login(
        self, request: AuthenticationRequest
    ) -> Optional[AuthenticationResponse]: ...


class MagicLinkStrategy:
    """Strategy for magic link authentication."""

    def __init__(self, handler: MagicLinkHandler):
        self.handler = handler

    async def handle_login(
        self, request: AuthenticationRequest
    ) -> Optional[AuthenticationResponse]:
        return await self.handler.authenticate(request)


class OTPStrategy:
    """Strategy for OTP authentication."""

    def __init__(self, handler: OTPHandler):
        self.handler = handler

    async def handle_login(
        self, request: AuthenticationRequest
    ) -> Optional[AuthenticationResponse]:
        return await self.handler.authenticate(request)


# Default strategy instances
magic_link_strategy = MagicLinkStrategy(MagicLinkHandler())
otp_strategy = OTPStrategy(OTPHandler())
