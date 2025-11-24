from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..admin_services import (
    AdminLoginService,
    InvalidCredentialsError,
    UserManagementService,
)
from ..auth import COOKIE_NAME
from ..config import settings
from ..grid_engine import GridEngine, PaginatedResponse
from ..i18n import gettext as _
from ..logger import get_logger
from ..models import Book, Car, Contact, User, UserBase, UserRole
from ..repository import get_session, get_user_by_email, list_contacts, list_users
from ..response_helpers import FormResponseHelper, ResponseHelper
from ..templates import templates
from ..users import require_admin

router = APIRouter()
logger = get_logger("admin")


# ============= Admin Auth Routes =============


@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_form(request: Request):
    """Display admin login form with optional 'next' parameter for post-login redirect"""
    return templates.TemplateResponse(
        "pages/admin/login.html", {"request": request, "error": None}
    )


@router.get("/admin/login-url")
async def admin_login_url(request: Request, next: Optional[str] = None):
    """Return just the next URL safely for JavaScript"""
    from urllib.parse import unquote

    if next:
        try:
            decoded = unquote(next)
            # Basic validation
            from urllib.parse import urlparse

            parsed = urlparse(decoded)
            if (
                parsed.scheme == ""
                and parsed.netloc == ""
                and parsed.path.startswith("/admin")
            ):
                return {"next_url": decoded}
        except Exception:
            pass
    return {"next_url": ""}


@router.post("/admin/login")
async def admin_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: Optional[str] = None,  # From query parameter (middleware)
    session: AsyncSession = Depends(get_session),
):
    """Bootstrap admin login with password (admin only)"""
    form_data = {"email": email, "password": password}

    login_service = AdminLoginService(session)

    try:
        # Check for next URL in cookie if not provided in params
        actual_next = next or request.cookies.get("next_url")

        # Authenticate user using service with guard clauses
        result = await login_service.authenticate(email, password, actual_next)

        # Return success response - JavaScript will handle redirect
        response = JSONResponse(
            content={"success": True, "redirect_url": result.redirect_url}
        )

        # Set session cookie on response
        response.set_cookie(
            COOKIE_NAME,
            result.session_cookie,
            httponly=True,
            samesite="lax",
            secure=not settings.debug,
        )

        # Clear next_url cookie if it exists
        response.delete_cookie("next_url")

        logger.info(f"Bootstrap admin logged in: {result.user.email}")
        return response

    except InvalidCredentialsError:
        # Return standardized error response using helper
        return ResponseHelper.validation_error(
            {"email": _("Invalid credentials")}, form_data
        )


@router.get("/admin/logout")
async def admin_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ============= Admin Dashboard & General =============


@router.get("/admin", response_class=HTMLResponse)
async def admin_index(
    request: Request,
    current_user: User = Depends(require_admin),
    session_db: AsyncSession = Depends(get_session),
):
    # show list of contacts
    contacts = await list_contacts(session_db, limit=100)
    return templates.TemplateResponse(
        "pages/admin/index.html",
        {"request": request, "contacts": contacts, "user": current_user},
    )


@router.get("/api/analytics/stats")
async def get_analytics_stats(session: AsyncSession = Depends(get_session)):
    """Get analytics statistics for dashboard"""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get user statistics
    total_users = await session.execute(select(User).where(User.is_active))
    total_users = len(total_users.scalars().all())

    # Get active users (created in the last week)
    active_users_query = select(User).where(User.is_active, User.created_at >= week_ago)
    active_users_result = await session.execute(active_users_query)
    active_users = len(active_users_result.scalars().all())

    # Get car statistics
    total_cars_query = select(Car)
    total_cars_result = await session.execute(total_cars_query)
    total_cars = len(total_cars_result.scalars().all())

    # Get cars added this month
    cars_this_month_query = select(Car).where(Car.created_at >= month_start)
    cars_this_month_result = await session.execute(cars_this_month_query)
    cars_this_month = len(cars_this_month_result.scalars().all())

    # Get book statistics
    total_books_query = select(Book)
    total_books_result = await session.execute(total_books_query)
    total_books = len(total_books_result.scalars().all())

    # Get books added this month
    books_this_month_query = select(Book).where(Book.created_at >= month_start)
    books_this_month_result = await session.execute(books_this_month_query)
    books_this_month = len(books_this_month_result.scalars().all())

    # Get contact statistics
    total_contacts_query = select(Contact)
    total_contacts_result = await session.execute(total_contacts_query)
    total_contacts = len(total_contacts_result.scalars().all())

    # Get contacts this week
    contacts_this_week_query = select(Contact).where(Contact.created_at >= week_ago)
    contacts_this_week_result = await session.execute(contacts_this_week_query)
    contacts_this_week = len(contacts_this_week_result.scalars().all())

    return {
        "users": {"total": total_users, "activeThisWeek": active_users},
        "cars": {"total": total_cars, "thisMonth": cars_this_month},
        "books": {"total": total_books, "thisMonth": books_this_month},
        "contacts": {"total": total_contacts, "thisWeek": contacts_this_week},
    }


@router.post("/admin/contact/delete", response_class=HTMLResponse)
async def admin_delete_contact(
    request: Request,
    id: int = Form(...),
    session=Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    # simple delete operation
    await db.execute(__import__("sqlmodel").sql.delete(Contact).where(Contact.id == id))  # type: ignore[arg-type]
    await db.commit()
    return RedirectResponse(url="/admin", status_code=303)


# ============= Admin User Management =============


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_list(
    request: Request,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin page to manage users"""
    users = await list_users(session, limit=200)
    return templates.TemplateResponse(
        "pages/admin/users.html",
        {"request": request, "users": users, "user": current_user},
    )


@router.get("/api/admin/users", response_model=PaginatedResponse[User])
async def get_users_grid(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "id",
    dir: str = "asc",
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """API endpoint for users data grid (admin only)"""
    grid = GridEngine(session, User)
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["email", "full_name"],
    )


@router.post("/api/admin/users", response_model=User)
async def create_user_api(
    user_data: UserBase,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Create a new user via REST API for datagrid"""
    logger.info(f"Creating user with data: {user_data}")

    # Check for email uniqueness
    existing = await get_user_by_email(session, user_data.email)
    if existing:
        raise HTTPException(
            status_code=400, detail=f"User with email {user_data.email} already exists"
        )

    # Create User instance from validated UserBase data
    user = User(**user_data.model_dump())
    # Set additional defaults not in UserBase
    user.email_verified = False
    user.is_verified = False
    user.hashed_password = ""

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.put("/api/admin/users/{user_id}", response_model=User)
async def update_user_api(
    user_id: int,
    user_data: UserBase,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Update an existing user via REST API for datagrid"""
    logger.info(f"Updating user {user_id} with data: {user_data}")

    # Get existing user
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from locking themselves out
    if user.id == current_user.id and not user_data.is_active:
        raise HTTPException(
            status_code=400, detail="Cannot deactivate your own account"
        )

    # Check email uniqueness if changing email
    if user_data.email != user.email:
        existing = await get_user_by_email(session, user_data.email)
        if existing and existing.id != user_id:
            raise HTTPException(
                status_code=400,
                detail=f"User with email {user_data.email} already exists",
            )

    # Only update fields that were provided (exclude_unset=True)
    update_data = user_data.model_dump(exclude_unset=True)
    protected_fields = {"id", "created_at", "updated_at", "hashed_password"}

    for key, value in update_data.items():
        if key not in protected_fields and hasattr(user, key):
            setattr(user, key, value)

    # Force email_verified to match is_verified when updating
    if "is_active" in update_data:
        user.is_verified = user.is_active

    user.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(user)
    return user


@router.delete("/api/admin/users/{user_id}")
async def delete_user_api(
    user_id: int,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Delete a user via REST API for datagrid"""
    logger.info(f"Deleting user {user_id}")

    # Get existing user
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    # Prevent deleting other admins if you're not admin (double protection)
    if user.role == UserRole.ADMIN and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403, detail="Insufficient privileges to delete admin users"
        )

    await session.delete(user)
    await session.commit()

    logger.info(f"Successfully deleted user {user_id}: {user.email}")
    return {"success": True, "message": "User deleted successfully"}


@router.post("/admin/users/{user_id}/approve")
async def admin_approve_user(
    user_id: int,
    role: UserRole = Form(UserRole.USER),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Approve a pending user and set their role"""
    user_service = UserManagementService(session)

    try:
        # Approve user using service with proper validation
        approved_user = await user_service.approve_user(user_id, role, current_user)

        # Return success response using helper
        return FormResponseHelper.form_success(
            message=_("User approved successfully"),
            user={
                "id": approved_user.id,
                "email": approved_user.email,
                "full_name": approved_user.full_name,
                "role": approved_user.role.value,
                "is_active": approved_user.is_active,
                "email_verified": approved_user.email_verified,
            },
        )
    except Exception as exc:
        logger.error(f"Failed to approve user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to approve user")


@router.post("/admin/users/create")
async def admin_create_user(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    role: UserRole = Form(...),
    password: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin creates a new user with optional password"""
    user_service = UserManagementService(session)

    try:
        # Create user using service with proper validation
        created_user = await user_service.create_user(
            email, full_name, role, password, current_user
        )

        # Return success response using helper
        return FormResponseHelper.form_success(
            message=_("User created successfully"),
            user={
                "id": created_user.id,
                "email": created_user.email,
                "full_name": created_user.full_name,
                "role": created_user.role.value,
                "is_active": created_user.is_active,
            },
        )
    except Exception as exc:
        logger.error(f"Failed to create user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.post("/admin/users/{user_id}/update-role")
async def admin_update_user_role(
    user_id: int,
    role: UserRole = Form(...),
    is_active: Optional[bool] = Form(None),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Update user role and active status"""
    user_service = UserManagementService(session)

    try:
        # Update user using service with safety checks
        updated_user = await user_service.update_user_role(
            user_id, role, is_active, current_user
        )

        # Return success response using helper
        return FormResponseHelper.form_success(
            message=_("User updated successfully"),
            user={
                "id": updated_user.id,
                "email": updated_user.email,
                "full_name": updated_user.full_name,
                "role": updated_user.role.value,
                "is_active": updated_user.is_active,
            },
        )
    except Exception as exc:
        logger.error(f"Failed to update user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update user")
