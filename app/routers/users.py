import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from ..i18n import gettext as _
from ..logger import get_logger
from ..models import User
from ..repository import get_session, get_user_by_email
from ..response_helpers import FormResponseHelper
from ..schemas import PasswordChange
from ..templates import templates
from ..users import current_active_user, password_helper

router = APIRouter()
logger = get_logger("users")


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    user: User = Depends(current_active_user),
):
    """Display user profile page"""
    return templates.TemplateResponse(
        "pages/profile.html",
        {
            "request": request,
            "user": user,
        },
    )


@router.post("/api/profile/update")
async def update_profile(
    request: Request,
    full_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Update user profile information"""
    form_data = {"full_name": full_name, "email": email, "phone": phone}

    # Update user fields if provided
    if full_name is not None:
        form_data["full_name"] = full_name
        if len(full_name.strip()) < 2:
            return FormResponseHelper.form_error(
                message=_("Name must be at least 2 characters"),
            )
        user.full_name = full_name.strip()

    if email is not None:
        # Basic email validation
        if "@" not in email or "." not in email:
            return FormResponseHelper.form_error(
                message=_("Invalid email address"),
            )
        # Check if email is already taken by another user
        existing = await get_user_by_email(session, email)
        if existing and existing.id != user.id:
            return FormResponseHelper.form_error(
                message=_("Email already in use by another account"),
                form_data=form_data,
            )
        user.email = email

    if phone is not None:
        # Basic phone validation (optional, just trim whitespace)
        phone = phone.strip()
        if phone and len(phone) > 20:
            return FormResponseHelper.form_error(
                message=_("Phone number too long (max 20 characters)"),
            )
        user.phone = phone if phone else None

    # Handle profile picture upload
    if profile_picture and profile_picture.filename:
        # Validate file type
        allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp"]
        if profile_picture.content_type not in allowed_types:
            return FormResponseHelper.form_error(
                message=_("Invalid file type. Please upload PNG, JPG, or WebP image."),
            )

        # Validate file size (5MB max)
        content = await profile_picture.read()
        if len(content) > 5 * 1024 * 1024:
            return FormResponseHelper.form_error(
                message=_("File too large. Maximum size is 5MB."),
            )

        # Save file to disk
        upload_dir = Path("static/uploads/profile_pictures")
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        file_ext = Path(profile_picture.filename).suffix
        unique_filename = f"{user.id}_{uuid.uuid4().hex[:8]}{file_ext}"
        file_path = upload_dir / unique_filename

        # Delete old profile picture if exists
        if user.profile_picture:
            old_file_path = Path(f"static{user.profile_picture}")
            if old_file_path.exists():
                old_file_path.unlink()

        # Write new file
        with open(file_path, "wb") as f:
            f.write(content)

        # Store relative path in database (must match static file mount at /static)
        user.profile_picture = f"/static/uploads/profile_pictures/{unique_filename}"

    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info(f"Profile updated for user: {user.email}")

    # Return profile picture URL if updated
    response_data = {"success": True, "message": _("Profile updated successfully")}
    if user.profile_picture:
        response_data["profile_picture"] = user.profile_picture

    return JSONResponse(content=response_data)


@router.post("/api/profile/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Change user password"""
    form_data = {
        "current_password": current_password,
        "new_password": new_password,
        "confirm_password": confirm_password,
    }

    # Validate with Pydantic
    try:
        payload = PasswordChange.model_validate(form_data)
    except ValidationError as e:
        return FormResponseHelper.form_error(
            message=_("Password change failed"),
            field_errors={str(error["loc"][-1]): error["msg"] for error in e.errors()},
        )

    # Verify current password
    if not user.hashed_password:
        return FormResponseHelper.form_error(
            message=_("No password set for this account. Use magic link login."),
        )

    is_valid, updated_hash = password_helper.verify_and_update(
        payload.current_password, user.hashed_password
    )

    if not is_valid:
        return FormResponseHelper.form_error(
            message=_("Password change failed"),
            field_errors={"current_password": _("Current password is incorrect")},
        )

    # Hash and set new password
    user.hashed_password = password_helper.hash(payload.new_password)
    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()

    logger.info(f"Password changed for user: {user.email}")
    return FormResponseHelper.form_success(message=_("Password changed successfully"))
