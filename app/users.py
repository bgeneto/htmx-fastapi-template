"""
FastAPI Users configuration and setup

This module configures fastapi-users for authentication and user management.
Integrates with the existing User model and provides authentication backends.
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi_users import BaseUserManager, FastAPIUsers, IntegerIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.password import PasswordHelper
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import settings
from .db_adapter import SQLModelUserDatabase
from .models import User, UserRole
from .repository import get_session

# Centralized password helper using pwdlib (Argon2 + Bcrypt)
# This replaces the old passlib-based password hashing
password_helper = PasswordHelper()


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    """User manager for handling user-related operations"""

    reset_password_token_secret = settings.SECRET_KEY.get_secret_value()
    verification_token_secret = settings.SECRET_KEY.get_secret_value()

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        """Hook called after user registration"""
        from .logger import get_logger

        logger = get_logger("users")
        logger.info(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Hook called after password reset request"""
        from .logger import get_logger

        logger = get_logger("users")
        logger.info(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Hook called after verification request"""
        from .logger import get_logger

        logger = get_logger("users")
        logger.info(
            f"Verification requested for user {user.id}. Verification token: {token}"
        )


async def get_user_db(session: AsyncSession = Depends(get_session)):
    """Dependency to get the user database adapter"""
    yield SQLModelUserDatabase(session, User)


async def get_user_manager(user_db=Depends(get_user_db)):
    """Dependency to get the user manager"""
    yield UserManager(user_db)


# Cookie-based authentication (for web UI)
cookie_transport = CookieTransport(
    cookie_name="session",
    cookie_max_age=settings.SESSION_EXPIRY_DAYS * 24 * 60 * 60,
    cookie_httponly=True,
    cookie_secure=not settings.debug,
    cookie_samesite="lax",
)


def get_jwt_strategy() -> JWTStrategy:
    """Get JWT strategy for authentication"""
    return JWTStrategy(
        secret=settings.SECRET_KEY.get_secret_value(),
        lifetime_seconds=settings.SESSION_EXPIRY_DAYS * 24 * 60 * 60,
    )


# Authentication backend using cookies
auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI Users instance
fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

# Current user dependencies
current_active_user = fastapi_users.current_user(active=True)
current_user_optional = fastapi_users.current_user(active=True, optional=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)


# Custom dependencies for role-based access
async def require_user(user: User = Depends(current_active_user)) -> User:
    """Dependency that requires any authenticated user"""
    return user


async def require_moderator(user: User = Depends(current_active_user)) -> User:
    """Dependency that requires moderator or admin role"""
    if user.role not in [UserRole.MODERATOR, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return user


async def require_admin(user: User = Depends(current_active_user)) -> User:
    """Dependency that requires admin role"""
    if user.role != UserRole.ADMIN and not user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
