import hashlib
import secrets
from datetime import datetime, timedelta
from typing import AsyncGenerator, Optional

from sqlalchemy import desc  # type: ignore[import]
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import settings
from .db import AsyncSessionLocal
from .logger import get_logger
from .models import Car, Contact, LoginToken, User, UserRole
from .schemas import AdminCreateUser, ContactCreate, UserRegister, UserUpdate

logger = get_logger("repo")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# ============= Password Hashing =============
# Password hashing is now delegated to fastapi-users' PasswordHelper
# which uses pwdlib (Argon2 + Bcrypt) instead of the deprecated passlib


def hash_password(password: str) -> str:
    """
    Hash password using fastapi-users' PasswordHelper (pwdlib with Argon2/Bcrypt).

    This replaces the old passlib-based sha256_crypt hashing.
    """
    from .users import password_helper

    return password_helper.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash using fastapi-users' PasswordHelper.

    Supports both new pwdlib hashes and legacy passlib hashes for backward compatibility.
    """
    from .users import password_helper

    # password_helper.verify returns tuple (verified, updated_hash)
    verified, _ = password_helper.verify_and_update(plain_password, hashed_password)
    return verified


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
        hashed_password=hashed_password or "",  # Empty string when no password provided
        is_verified=False,
        email_verified=False,
        is_active=True,
        is_superuser=(role == UserRole.ADMIN) if role else False,
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(f"Created user: {user.email} with role {user.role}")
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Get user by email address with Redis caching."""
    from .redis_utils import user_cache

    # Try cache first
    cache_key = f"user_by_email:{email.lower()}"
    cached_user = await user_cache.get(cache_key)
    if cached_user:
        # Convert cached dict back to User object
        user = User(**cached_user)
        return user

    # Cache miss - query database
    result = await session.exec(select(User).where(User.email == email.lower()))
    user = result.one_or_none()

    # Cache the result (if found)
    if user:
        user_dict = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "role": user.role,
            "hashed_password": user.hashed_password,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }
        await user_cache.set(cache_key, user_dict)

    return user


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
    """Update user details with cache invalidation."""
    from .redis_utils import user_cache

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = payload.role
        # Sync is_superuser with ADMIN role
        user.is_superuser = payload.role == UserRole.ADMIN
    if payload.is_active is not None:
        user.is_active = payload.is_active

    user.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(user)

    # Invalidate user cache
    cache_key = f"user_by_email:{user.email.lower()}"
    await user_cache.delete(cache_key)

    logger.info(f"Updated user {user.email}")
    return user


async def approve_user(
    session: AsyncSession, user: User, role: UserRole = UserRole.USER
) -> User:
    """Approve a pending user by setting their role"""
    user.role = role
    user.is_verified = True
    user.email_verified = True
    # Sync is_superuser with ADMIN role
    user.is_superuser = role == UserRole.ADMIN
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


# ============= Car CRUD =============


async def create_car(
    session: AsyncSession, make: str, model: str, version: str, year: int, price: float
) -> Car:
    """Create a new car"""
    car = Car(make=make, model=model, version=version, year=year, price=price)
    session.add(car)
    await session.commit()
    await session.refresh(car)
    return car


async def list_cars(session: AsyncSession, limit: int = 100) -> list[Car]:
    """List all cars"""
    result = await session.exec(select(Car).order_by(desc(Car.id)).limit(limit))  # type: ignore[arg-type]
    return list(result.all())


async def seed_cars(session: AsyncSession, count: int = 500):
    """Seed database with fake cars using faker"""
    try:
        from faker import Faker
    except ImportError:
        logger.warning("Faker not installed, skipping car seeding")
        return

    # Check if cars already exist
    result = await session.exec(select(Car).limit(1))
    if result.first():
        logger.info("Cars already exist, skipping seed")
        return

    faker = Faker()

    # Car makes and models
    cars_data = [
        ("Toyota", ["Camry", "Corolla", "RAV4", "Civic", "Accord"]),
        ("Honda", ["Civic", "Accord", "CR-V", "Pilot", "Fit"]),
        ("Ford", ["Mustang", "F-150", "Explorer", "Escape", "Fusion"]),
        ("BMW", ["3 Series", "5 Series", "X5", "X3", "M340i"]),
        ("Mercedes", ["C-Class", "E-Class", "GLE", "A-Class", "GLA"]),
        ("Audi", ["A4", "A6", "Q5", "Q7", "A8"]),
        ("Tesla", ["Model 3", "Model Y", "Model S", "Model X", "Roadster"]),
        ("Volkswagen", ["Golf", "Passat", "Tiguan", "Jetta", "Beetle"]),
        ("Hyundai", ["Elantra", "Sonata", "Tucson", "Santa Fe", "Kona"]),
        ("Kia", ["Forte", "Optima", "Sportage", "Sorento", "Niro"]),
    ]

    cars = []
    for i in range(count):
        make, models = faker.random.choice(cars_data)
        model = faker.random.choice(models)
        version = faker.random.choice(
            ["LE", "SE", "XLE", "Sport", "Limited", "Platinum", "GT", "RS"]
        )
        year = faker.random.randint(2010, 2024)
        price = faker.random.uniform(15000, 150000)

        cars.append(
            Car(
                make=make,
                model=model,
                version=version,
                year=year,
                price=round(price, 2),
            )
        )

    session.add_all(cars)
    await session.commit()
    logger.info(f"Seeded {count} cars")


# ============= Book CRUD =============


from .models import Book


async def create_book(
    session: AsyncSession, title: str, author: str, year: int, pages: int, summary: str
) -> Book:
    """Create a new book"""
    book = Book(title=title, author=author, year=year, pages=pages, summary=summary)
    session.add(book)
    await session.commit()
    await session.refresh(book)
    return book


async def list_books(session: AsyncSession, limit: int = 100):
    """List all books"""
    result = await session.exec(select(Book).order_by(desc(Book.id)).limit(limit))  # type: ignore[arg-type]
    return result.all()


async def seed_books(session: AsyncSession, count: int = 100):
    """Seed database with fake books using faker"""
    try:
        from faker import Faker
    except ImportError:
        logger.warning("Faker not installed, skipping book seeding")
        return

    # Check if books already exist
    result = await session.exec(select(Book).limit(1))
    if result.first():
        logger.info("Books already exist, skipping seed")
        return

    faker = Faker()

    books = []
    for i in range(count):
        title = faker.catch_phrase()  # More realistic book-like titles
        author = faker.name()
        year = faker.random_int(min=1800, max=2024)
        pages = faker.random_int(min=100, max=1000)
        summary = faker.text(max_nb_chars=500)

        books.append(
            Book(title=title, author=author, year=year, pages=pages, summary=summary)
        )

    session.add_all(books)
    await session.commit()
    logger.info(f"Seeded {count} books")
