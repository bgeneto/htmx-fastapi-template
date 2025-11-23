"""
Configuration and setup for fastapi-otp-auth integration.

This module provides the configuration wrapper for fastapi-otp-auth with Redis backend
and JWT token compatibility with fastapi-users.
"""

import os
from fastapi_otp_auth import Settings, auth_router

from .config import settings


def setup_otp_config():
    """Configure fastapi-otp-auth environment variables using our settings."""

    # Set up environment variables for fastapi-otp-auth
    # These are automatically picked up by the Settings class
    os.environ["REDIS_URL"] = settings.REDIS_URL
    os.environ["JWT_SECRET"] = settings.SECRET_KEY.get_secret_value()
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = str(settings.SESSION_EXPIRY_DAYS * 24 * 60)  # days to minutes
    os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = str(settings.SESSION_EXPIRY_DAYS)
    os.environ["OTP_EXPIRY_SECONDS"] = str(settings.OTP_EXPIRY_MINUTES * 60)  # minutes to seconds


async def send_otp_email_custom(email: str, otp_code: str) -> bool:
    """
    Send OTP email using existing Resend integration.
    This function will be used as a custom email sender for fastapi-otp-auth.

    Args:
        email: Recipient email address
        otp_code: 6-digit OTP code

    Returns:
        True if email sent successfully, False otherwise
    """
    from .email import send_otp_email

    # Get user name from database if possible, otherwise use default
    from .repository import get_user_by_email
    from .db import get_async_session

    full_name = "User"  # Default fallback

    try:
        async for session in get_async_session():
            user = await get_user_by_email(session, email)
            if user:
                full_name = user.full_name
            break
    except Exception:
        # If we can't get the user name, continue with default
        pass

    return await send_otp_email(email, full_name, otp_code)


# Initialize OTP configuration
setup_otp_config()

# Get the auth router - this is the main entry point for fastapi-otp-auth
otp_router = auth_router

# Create a settings instance to validate configuration
otp_settings = Settings(
    redis_url=settings.REDIS_URL,
    jwt_secret=settings.SECRET_KEY.get_secret_value(),
    jwt_algorithm="HS256",
    access_token_expire_minutes=settings.SESSION_EXPIRY_DAYS * 24 * 60,
    refresh_token_expire_days=settings.SESSION_EXPIRY_DAYS,
    otp_expiry_seconds=settings.OTP_EXPIRY_MINUTES * 60,
)
