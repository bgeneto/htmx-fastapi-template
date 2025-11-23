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
    Queue OTP email for background processing using Resend integration.

    Args:
        email: Recipient email address
        otp_code: 6-digit OTP code

    Returns:
        True if email queued successfully, False otherwise
    """
    from .email_worker import queue_otp_email

    # Get user name from database if possible, otherwise use default
    from .repository import get_user_by_email
    from .db import AsyncSessionLocal

    full_name = None  # Will be filled by worker if not provided

    try:
        async with AsyncSessionLocal() as session:
            user = await get_user_by_email(session, email)
            if user:
                full_name = user.full_name
    except Exception:
        # If we can't get the user name, continue with default
        pass

    return await queue_otp_email(email, otp_code, full_name)


async def request_otp_with_resend(email: str) -> dict:
    """
    Custom OTP request that uses our Resend email integration instead of fastapi-otp-auth's SMTP.

    Args:
        email: User's email address

    Returns:
        Success response with status
    """
    try:
        # Import here to avoid circular imports
        import redis.asyncio as redis
        from .config import settings

        # Connect to Redis directly
        client = redis.from_url(settings.REDIS_URL)

        # Generate a 6-digit OTP code
        import random
        otp_code = f"{random.randint(0, 999999):06d}"

        # Store OTP in Redis with expiry
        key = f"otp:{email.lower()}"
        await client.setex(key, settings.OTP_EXPIRY_MINUTES * 60, otp_code)

        # Queue email with our Resend integration
        success = await send_otp_email_custom(email, otp_code)

        await client.close()

        if success:
            return {"status": "success", "message": "OTP code sent successfully"}
        else:
            return {"status": "error", "message": "Failed to send OTP email"}

    except Exception as e:
        from .logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"Error requesting OTP with Resend: {e}")
        return {"status": "error", "message": "Failed to generate OTP code"}


async def verify_otp_with_resend(email: str, otp_code: str) -> dict:
    """
    Custom OTP verification that works with our Resend-sent codes.

    Args:
        email: User's email address
        otp_code: 6-digit OTP code from user

    Returns:
        Verification response with JWT tokens if successful
    """
    try:
        import redis.asyncio as redis
        from .config import settings
        import jwt
        from datetime import datetime, timedelta
        from .repository import get_user_by_email
        from .db import AsyncSessionLocal

        # Connect to Redis directly
        client = redis.from_url(settings.REDIS_URL)

        # Get stored OTP
        key = f"otp:{email.lower()}"
        stored_otp = await client.get(key)

        if not stored_otp or stored_otp != otp_code:
            await client.close()
            return {"status": "error", "message": "Invalid or expired OTP code"}

        # Delete OTP after successful verification
        await client.delete(key)
        await client.close()

        # Get user from database
        async with AsyncSessionLocal() as session:
            user = await get_user_by_email(session, email)
            if not user:
                return {"status": "error", "message": "User not found"}

            if not user.is_active:
                return {"status": "error", "message": "Account is not active"}

            # Generate JWT tokens compatible with fastapi-users
            now = datetime.utcnow()
            access_token_expire = now + timedelta(minutes=settings.SESSION_EXPIRY_DAYS * 24 * 60)
            refresh_token_expire = now + timedelta(days=settings.SESSION_EXPIRY_DAYS)

            token_data = {
                "sub": str(user.id),
                "email": user.email,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "iat": now,
                "exp": access_token_expire
            }

            access_token = jwt.encode(token_data, settings.SECRET_KEY.get_secret_value(), algorithm="HS256")

            refresh_token_data = token_data.copy()
            refresh_token_data["exp"] = refresh_token_expire
            refresh_token = jwt.encode(refresh_token_data, settings.SECRET_KEY.get_secret_value(), algorithm="HS256")

            return {
                "status": "success",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user_id": user.id
            }

    except jwt.ExpiredSignatureError:
        return {"status": "error", "message": "Token has expired"}
    except jwt.InvalidTokenError:
        return {"status": "error", "message": "Invalid token"}
    except Exception as e:
        from .logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"Error verifying OTP with Resend: {e}")
        return {"status": "error", "message": "Failed to verify OTP code"}


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
