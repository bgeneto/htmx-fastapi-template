from typing import Optional, Protocol

from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from .i18n import gettext as _
from .models import UserRole


class AuthenticationRequest:
    def __init__(self, email: str, session: AsyncSession):
        self.email = email
        self.session = session


class AuthenticationResponse(Protocol):
    def to_response(self) -> JSONResponse: ...


class SuccessResponse:
    def __init__(self, message: str):
        self.message = message

    def to_response(self) -> JSONResponse:
        return JSONResponse(content={"success": True, "message": self.message})


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

            # Send magic link email
            await send_magic_link(user.email, user.full_name, magic_link)
        else:
            # Log warning for non-existent/inactive user (for monitoring)
            pass

        # Always show check email page
        return None  # Signal to redirect to check email page


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


# Default strategy instance
default_auth_strategy = MagicLinkStrategy(MagicLinkHandler())
