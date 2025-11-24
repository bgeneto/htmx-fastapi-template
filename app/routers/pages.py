from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..i18n import gettext as _
from ..logger import get_logger
from ..models import User
from ..repository import get_session
from ..templates import templates
from ..users import current_user_optional

router = APIRouter()
logger = get_logger("pages")


@router.get("/health")
async def healthcheck(session: AsyncSession = Depends(get_session)):
    """Health check endpoint that tests database connectivity"""
    try:
        # Test database connection with a simple query
        await session.execute(select(1))
        return {"status": "healthy"}
    except Exception as exc:
        logger.error(f"Health check failed: {exc}")
        raise HTTPException(status_code=503, detail="Database connection failed")


@router.get("/")
async def root(request: Request, user: Optional[User] = Depends(current_user_optional)):
    """Analytics dashboard as default home page"""
    return templates.TemplateResponse(
        "pages/analytics.html",
        {"request": request, "user": user},
    )
