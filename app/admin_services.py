"""Admin service objects for separating business logic from endpoints

This module provides service classes that handle complex business logic
for admin operations, reducing complexity in route handlers.
"""

from typing import Optional

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .auth import create_session_cookie
from .strategies import create_admin_login_verifier
from .models import User
from .repository import get_user_by_email
from .url_validator import validate_admin_redirect


class InvalidCredentialsError(Exception):
    """Exception raised when admin credentials are invalid"""

    pass


class LoginResult:
    """Result of admin login operation"""

    def __init__(
        self, success: bool, redirect_url: str, session_cookie: str, user: User
    ):
        self.success = success
        self.redirect_url = redirect_url
        self.session_cookie = session_cookie
        self.user = user


class AdminLoginService:
    """Service for handling admin login with proper separation of concerns"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def authenticate(
        self, email: str, password: str, next_url: Optional[str] = None
    ) -> LoginResult:
        """
        Authenticate admin user with guard clauses for early returns

        Args:
            email: Admin email address
            password: Admin password
            next_url: Optional redirect URL after successful login

        Returns:
            LoginResult with authentication outcome

        Raises:
            InvalidCredentialsError: If credentials are invalid
            HTTPException: If user not found or other errors
        """
        # Guard clause: Get user or raise early
        user = await self._get_user_or_404(email)

        # Guard clause: Validate credentials or raise early
        self._validate_credentials(user, password)

        # Guard clause: Determine redirect URL
        redirect_url = self._determine_redirect_url(next_url)

        # Create session cookie
        session_cookie = create_session_cookie(user.id, user.email, user.role)

        return LoginResult(
            success=True,
            redirect_url=redirect_url,
            session_cookie=session_cookie,
            user=user,
        )

    async def _get_user_or_404(self, email: str) -> User:
        """
        Get user by email or raise 404 if not found

        Args:
            email: Email address to look up

        Returns:
            User object if found

        Raises:
            HTTPException: If user not found
        """
        user = await get_user_by_email(self.session, email)
        if not user:
            raise HTTPException(status_code=400, detail="Invalid credentials")
        return user

    def _validate_credentials(self, user: User, password: str) -> None:
        """
        Validate user credentials using verifier strategy

        Args:
            user: User object to validate
            password: Password to verify

        Raises:
            InvalidCredentialsError: If credentials are invalid
        """
        verifier = create_admin_login_verifier(user)
        if not verifier.verify(password=password):
            raise InvalidCredentialsError()

    def _determine_redirect_url(self, next_url: Optional[str]) -> str:
        """
        Determine safe redirect URL after login

        Args:
            next_url: Optional next URL from request parameters

        Returns:
            Safe redirect URL (default to /admin if invalid)
        """
        if not next_url:
            return "/admin"

        # Use centralized URL validation
        return validate_admin_redirect(next_url, "/admin")


class UserManagementService:
    """Service for user management operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def approve_user(self, user_id: int, role, admin_user: User):
        """
        Approve a pending user with proper validation

        Args:
            user_id: ID of user to approve
            role: Role to assign to user
            admin_user: Admin user performing the approval

        Returns:
            Updated user object

        Raises:
            HTTPException: If user not found or not pending
        """
        from .config import settings
        from .email import send_account_approved
        from .i18n import gettext as _
        from .repository import approve_user as repo_approve_user
        from .repository import get_user_by_id

        user = await get_user_by_id(self.session, user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.role.value != "PENDING":  # Compare with enum value
            raise HTTPException(
                status_code=400, detail=_("User is not pending approval")
            )

        # Approve user using repository function
        approved_user = await repo_approve_user(self.session, user, role)

        # Send approval notification
        login_url = f"{settings.APP_BASE_URL}/auth/login"
        await send_account_approved(user.email, user.full_name, login_url)

        # Log the approval
        from .logger import get_logger

        logger = get_logger("admin_services")
        logger.info(f"User {user.email} approved by {admin_user.email}")

        return approved_user

    async def create_user(
        self,
        email: str,
        full_name: str,
        role,
        password: Optional[str],
        admin_user: User,
    ):
        """
        Create a new user with proper validation

        Args:
            email: User email address
            full_name: User full name
            role: User role to assign
            password: Optional password (can be None for magic link users)
            admin_user: Admin user creating the account

        Returns:
            Created user object

        Raises:
            HTTPException: If user already exists or validation fails
        """
        from .i18n import gettext as _
        from .repository import create_user as repo_create_user
        from .repository import get_user_by_email, hash_password

        form_data = {
            "email": email,
            "full_name": full_name,
            "role": role,
            "password": password,
        }

        # Check if user exists
        existing_user = await get_user_by_email(self.session, email)
        if existing_user:
            raise HTTPException(
                status_code=400, detail=_("User with this email already exists")
            )

        # Hash password if provided
        hashed_password = hash_password(password) if password else None

        # Create user using repository function
        user = await repo_create_user(
            self.session,
            # Convert to appropriate schema - assuming AdminCreateUser-like structure
            type(
                "UserCreate",
                (),
                {
                    "email": str,
                    "full_name": str,
                    "role": type,
                    "password": Optional[str],
                },
            )(**form_data),
            role=role,
            hashed_password=hashed_password,
        )

        # Mark as verified since admin created it
        user.email_verified = True
        await self.session.commit()

        # Log the creation
        from .logger import get_logger

        logger = get_logger("admin_services")
        logger.info(f"Admin {admin_user.email} created user {user.email}")

        return user

    async def update_user_role(
        self, user_id: int, role, is_active: Optional[bool], admin_user: User
    ):
        """
        Update user role and active status with safety checks

        Args:
            user_id: ID of user to update
            role: New role for user
            is_active: Optional active status
            admin_user: Admin user performing the update

        Returns:
            Updated user object

        Raises:
            HTTPException: If user not found or safety check fails
        """
        from .i18n import gettext as _
        from .repository import get_user_by_id, update_user

        user = await get_user_by_id(self.session, user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Prevent admin from deactivating themselves
        if user.id == admin_user.id and is_active is False:
            raise HTTPException(
                status_code=400, detail=_("You cannot deactivate your own account")
            )

        # Update user
        from .schemas import UserUpdate

        update_data = UserUpdate(role=role, is_active=is_active, full_name=None)
        updated_user = await update_user(self.session, user, update_data)

        # Log the update
        from .logger import get_logger

        logger = get_logger("admin_services")
        logger.info(f"Admin {admin_user.email} updated user {updated_user.email}")

        return updated_user


class CarManagementService:
    """Service for car management operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def delete_car(self, car_id: int):
        """
        Delete a car with proper validation and error handling

        Args:
            car_id: ID of car to delete

        Returns:
            Success message

        Raises:
            HTTPException: If car not found or deletion fails
        """
        from sqlalchemy import delete

        from .logger import get_logger
        from .models import Car

        # First check if car exists
        result = await self.session.execute(select(Car).where(Car.id == car_id))
        car = result.scalar_one_or_none()

        if not car:
            raise HTTPException(status_code=404, detail="Car not found")

        try:
            # Use raw SQL delete with proper SQLAlchemy import
            await self.session.execute(delete(Car).where(Car.id == car_id))
            await self.session.commit()

            # Verify deletion by checking if car still exists
            verify_result = await self.session.execute(
                select(Car).where(Car.id == car_id)
            )
            if verify_result.scalar_one_or_none() is not None:
                await self.session.rollback()
                raise HTTPException(
                    status_code=500, detail="Failed to delete car from database"
                )

            logger = get_logger("admin_services")
            logger.info(
                f"Successfully deleted car ID {car_id}: {car.make} {car.model} ({car.year})"
            )

            return {"success": True, "message": "Car deleted successfully"}

        except Exception as e:
            await self.session.rollback()
            logger = get_logger("admin_services")
            logger.error(f"Failed to delete car ID {car_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to delete car: {str(e)}"
            )
