from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from ..grid_engine import GridEngine, PaginatedResponse
from ..i18n import gettext as _
from ..logger import get_logger
from ..models import Contact, User
from ..repository import create_contact, get_session
from ..response_helpers import ResponseHelper
from ..schemas import ContactCreate
from ..templates import templates
from ..users import current_user_optional

router = APIRouter()
logger = get_logger("contacts")


@router.get("/contact", response_class=HTMLResponse)
async def index(
    request: Request,
    user: Optional[User] = Depends(current_user_optional),
    session: AsyncSession = Depends(get_session),
):
    response = templates.TemplateResponse(
        "pages/contact.html",
        {
            "request": request,
            "user": user,
        },
    )
    # Cache headers for improved performance
    response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    return response


@router.post("/contact")
async def contact(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    form_data = {"name": name, "email": email, "message": message}
    logger.info(
        "Form submission received: name={}, email={}, message_length={}",
        form_data["name"],
        form_data["email"],
        len(form_data["message"] or ""),
    )

    # Server-side validation with Pydantic
    try:
        payload = ContactCreate.model_validate(form_data)
        logger.info("Form validation successful for user: {}", form_data["email"])
    except ValidationError as e:
        logger.warning(
            "Form validation failed for: email={}, errors={}",
            form_data["email"],
            str(e),
        )
        # Return JSON for Alpine.js using helper
        return ResponseHelper.pydantic_validation_error(e, form_data)

    # Persist contact
    try:
        contact = await create_contact(session, payload)
        logger.info(
            "Contact successfully saved: email={}, id={}",
            form_data["email"],
            contact.id,
        )
    except Exception as exc:
        logger.error("Failed to save contact: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to save contact")

    # Return JSON for Alpine.js
    return JSONResponse(
        content={
            "success": True,
            "contact": {
                "id": contact.id,
                "name": contact.name,
                "email": contact.email,
                "message": contact.message,
            },
        }
    )


@router.get("/contacts", response_class=HTMLResponse)
async def contacts_page(
    request: Request,
    user: Optional[User] = Depends(current_user_optional),
):
    """Display contacts directory page with data grid"""
    return templates.TemplateResponse(
        "pages/contacts.html",
        {
            "request": request,
            "user": user,
            "api_url": "/api/contacts",
            "columns": [
                {"key": "id", "label": _("ID"), "width": 70, "sortable": True},
                {
                    "key": "name",
                    "label": _("Name"),
                    "width": 200,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "email",
                    "label": _("Email"),
                    "width": 250,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "message",
                    "label": _("Message"),
                    "width": 300,
                    "sortable": False,
                },
                {
                    "key": "created_at",
                    "label": _("Submitted"),
                    "width": 180,
                    "sortable": True,
                },
            ],
            "search_placeholder": _("Search by name or email..."),
        },
    )


@router.get("/api/contacts", response_model=PaginatedResponse[Contact])
async def get_contacts_grid(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "id",
    dir: str = "asc",
    session: AsyncSession = Depends(get_session),
):
    """API endpoint for contacts data grid with server-side pagination, filtering, and sorting"""
    grid = GridEngine(session, Contact)
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["name", "email"],
    )
