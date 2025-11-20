import hashlib
import secrets
from datetime import datetime, timedelta
from typing import AsyncGenerator, Optional

from passlib.context import CryptContext
from sqlalchemy import desc  # type: ignore[import]
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import settings
from .db import AsyncSessionLocal
from .logger import get_logger
from .models import Contact, LoginToken, User, UserRole
from .schemas import AdminCreateUser, ContactCreate, UserRegister, UserUpdate

logger = get_logger("repo")

# Password hashing context (for bootstrap admin and admin-created users)
# Using sha256_crypt instead of bcrypt due to bcrypt library issues
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# ============= Password Hashing =============


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


# ============= User CRUD =============


async def create_user(
    session: AsyncSession,
    payload: UserRegister | AdminCreateUser,
    role: Optional[UserRole] = None,
    hashed_password: Optional[str] = None,
) -> User:
    """
    Create a new user

    Args:
        session: Database session
        payload: User registration data
        role: Override role (for admin-created users)
        hashed_password: Pre-hashed password (for admin-created users)
    """
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        role=(
            role
            if role is not None
            else (
                payload.role
                if isinstance(payload, AdminCreateUser)
                else UserRole.PENDING
            )
        ),
        hashed_password=hashed_password,
        email_verified=False,
        is_active=True,
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(f"Created user: {user.email} with role {user.role}")
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Get user by email address"""
    result = await session.exec(select(User).where(User.email == email.lower()))
    return result.one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID"""
    result = await session.exec(select(User).where(User.id == user_id))
    return result.one_or_none()


async def list_users(
    session: AsyncSession, role_filter: Optional[UserRole] = None, limit: int = 100
) -> list[User]:
    """List all users, optionally filtered by role"""
    query = select(User).order_by(desc(User.created_at)).limit(limit)  # type: ignore[arg-type]

    if role_filter:
        query = query.where(User.role == role_filter)

    result = await session.exec(query)
    return list(result.all())


async def update_user(session: AsyncSession, user: User, payload: UserUpdate) -> User:
    """Update user details"""
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active

    user.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(user)
    logger.info(f"Updated user {user.email}")
    return user


async def approve_user(
    session: AsyncSession, user: User, role: UserRole = UserRole.USER
) -> User:
    """Approve a pending user by setting their role"""
    user.role = role
    user.email_verified = True
    user.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(user)
    logger.info(f"Approved user {user.email} with role {role}")
    return user


# ============= Magic Link Token Management =============


def _hash_token(token: str) -> str:
    """Hash token for secure storage using SHA-256"""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_login_token(session: AsyncSession, user: User) -> str:
    """
    Create a magic link token for user

    Returns:
        Raw token string (to be sent in email, not stored)
    """
    # Generate secure random token
    raw_token = secrets.token_urlsafe(32)

    # Hash token for storage
    token_hash = _hash_token(raw_token)

    # Calculate expiration
    expires_at = datetime.utcnow() + timedelta(
        minutes=settings.MAGIC_LINK_EXPIRY_MINUTES
    )

    # Create token record
    assert user.id is not None
    login_token = LoginToken(
        user_id=user.id, token_hash=token_hash, expires_at=expires_at
    )

    session.add(login_token)
    await session.commit()

    logger.info(f"Created magic link token for user {user.email}")
    return raw_token


async def get_valid_token(
    session: AsyncSession, raw_token: str
) -> Optional[tuple[LoginToken, User]]:
    """
    Validate magic link token and return associated user

    Args:
        session: Database session
        raw_token: Raw token from URL

    Returns:
        Tuple of (LoginToken, User) if valid, None otherwise
    """
    token_hash = _hash_token(raw_token)

    # Find unexpired, unused token
    result = await session.exec(
        select(LoginToken)
        .where(LoginToken.token_hash == token_hash)
        .where(LoginToken.used_at.is_(None))  # type: ignore[union-attr]
        .where(LoginToken.expires_at > datetime.utcnow())
    )

    login_token = result.one_or_none()

    if not login_token:
        logger.warning("Invalid or expired token attempted")
        return None

    # Get associated user
    user = await get_user_by_id(session, login_token.user_id)

    if not user or not user.is_active:
        logger.warning(
            f"Token valid but user inactive or not found: {login_token.user_id}"
        )
        return None

    return (login_token, user)


async def mark_token_used(session: AsyncSession, login_token: LoginToken) -> None:
    """Mark a login token as used"""
    login_token.used_at = datetime.utcnow()
    await session.commit()
    logger.info(f"Marked token {login_token.id} as used")


# ============= Contact CRUD (existing) =============


async def create_contact(session: AsyncSession, payload: ContactCreate) -> Contact:
    contact = Contact.from_orm(payload)  # SQLModel compatible
    session.add(contact)
    await session.commit()
    await session.refresh(contact)
    logger.debug("Created contact: {}", contact.id)
    return contact


async def list_contacts(session: AsyncSession, limit: int = 100):
    """Get contacts ordered by ID descending"""
    result = await session.exec(
        select(Contact).order_by(desc(Contact.id)).limit(limit)  # type: ignore[arg-type]
    )
    return result.all()


async def get_recent_contacts(session: AsyncSession, limit: int = 4):
    """Get the most recent contacts ordered by creation date"""
    return await list_contacts(session, limit=limit)
