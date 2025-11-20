from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, URLSafeSerializer
from sqlmodel.ext.asyncio.session import AsyncSession

from . import repository
from .config import settings
from .models import User, UserRole

COOKIE_NAME = "session"

_serializer = URLSafeSerializer(
    settings.SECRET_KEY.get_secret_value(), salt="session-salt"
)


def create_session_cookie(user_id: int, email: str, role: UserRole) -> str:
    """
    Create session cookie with user data and expiration

    Args:
        user_id: User's database ID
        email: User's email address
        role: User's role

    Returns:
        Signed session cookie string
    """
    expires_at = datetime.utcnow() + timedelta(days=settings.SESSION_EXPIRY_DAYS)

    data = {
        "user_id": user_id,
        "email": email,
        "role": role.value,
        "expires_at": expires_at.isoformat(),
    }

    return _serializer.dumps(data)


def load_session_cookie(s: str) -> Optional[dict]:
    """
    Load and validate session cookie

    Returns:
        Session data dict if valid and not expired, None otherwise
    """
    try:
        data = _serializer.loads(s)

        # Check expiration
        expires_at = datetime.fromisoformat(data["expires_at"])
        if expires_at < datetime.utcnow():
            return None

        return data
    except (BadSignature, KeyError, ValueError):
        return None


async def get_current_user(
    request: Request, session: AsyncSession = Depends(repository.get_session)
) -> Optional[User]:
    """
    Get current authenticated user from session cookie

    Returns:
        User object if authenticated, None otherwise
    """
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None

    session_data = load_session_cookie(cookie)
    if not session_data:
        return None

    user_id = session_data.get("user_id")
    if not user_id:
        return None

    # Get fresh user data from database
    user = await repository.get_user_by_id(session, user_id)

    # Verify user is still active
    if not user or not user.is_active:
        return None

    return user


async def require_user(
    request: Request, session: AsyncSession = Depends(repository.get_session)
) -> User:
    """
    Dependency that requires any authenticated user

    Raises:
        HTTPException: 401 if not authenticated
    """
    user = await get_current_user(request, session)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def require_moderator(
    request: Request, session: AsyncSession = Depends(repository.get_session)
) -> User:
    """
    Dependency that requires moderator or admin role

    Raises:
        HTTPException: 401 if not authenticated, 403 if insufficient permissions
    """
    user = await get_current_user(request, session)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if user.role not in [UserRole.MODERATOR, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return user


async def require_admin(
    request: Request, session: AsyncSession = Depends(repository.get_session)
) -> User:
    """
    Dependency that requires admin role

    Raises:
        HTTPException: 401 if not authenticated, 403 if not admin
    """
    user = await get_current_user(request, session)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")

    return user
