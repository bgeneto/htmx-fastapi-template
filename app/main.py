from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .db import init_db
from .i18n import get_locale, get_translations, set_locale
from .logger import get_logger
from .models import Contact
from .repository import create_contact, get_session, list_contacts
from .schemas import ContactCreate

logger = get_logger("main")

app = FastAPI(title=settings.app_name, debug=settings.debug)
templates = Jinja2Templates(directory="templates")

# Configure Jinja2 with i18n extension
templates.env.add_extension("jinja2.ext.i18n")
templates.env.install_gettext_callables(
    gettext=lambda x: get_translations(get_locale()).gettext(x),
    ngettext=lambda s, p, n: get_translations(get_locale()).ngettext(s, p, n),
    newstyle=True,
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# Middleware for locale detection
class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Try to get locale from cookie first
        locale = request.cookies.get("locale")

        # Fall back to Accept-Language header
        if not locale:
            accept_language = request.headers.get("Accept-Language", "en")
            # Parse Accept-Language header (simple parsing)
            locale = accept_language.split(",")[0].split(";")[0].strip()
            # Normalize locale (e.g., en-US -> en, pt-BR -> pt_BR)
            if "-" in locale:
                parts = locale.split("-")
                if len(parts[1]) == 2 and parts[1].isupper():
                    # Country code: pt-BR -> pt_BR
                    locale = f"{parts[0]}_{parts[1]}"
                else:
                    # Language only: en-US -> en
                    locale = parts[0]

        # Set locale for this request
        set_locale(locale)

        # Make locale available in request state
        request.state.locale = locale

        response = await call_next(request)
        return response


app.add_middleware(LocaleMiddleware)


# Startup event
@app.on_event("startup")
async def startup_event():
    # For development convenience; in production use alembic migrations
    try:
        await init_db()
        logger.info("DB initialized on startup")
    except Exception as e:
        logger.error("DB init failed: {}", e)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "errors": {}, "form": {}}
    )


@app.post("/contact", response_class=HTMLResponse)
async def contact(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    form_data = {"name": name, "email": email, "message": message}
    # Server-side validation with Pydantic
    try:
        payload = ContactCreate.model_validate(form_data)
    except ValidationError as e:
        errors = (
            {
                err["loc"][0]: err["msg"]
                for err in e.model_dump().get("__pydantic_validation_errors__", [])
            }
            if hasattr(e, "model_dump")
            else {}
        )
        # Fallback: use pydantic's errors() if available
        try:
            errors = {err["loc"][-1]: err["msg"] for err in e.errors()}
        except Exception:
            errors = {"__all__": str(e)}
        context = {"request": request, "errors": errors, "form": form_data}
        if request.headers.get("hx-request"):
            return templates.TemplateResponse("_form.html", context)
        return templates.TemplateResponse("index.html", context)

    # persist contact
    try:
        contact = await create_contact(session, payload)
    except Exception as exc:
        logger.error("Failed to save contact: {}", exc)
        raise HTTPException(status_code=500, detail="Failed to save contact")

    ctx = {"request": request, "contact": contact}
    if request.headers.get("hx-request"):
        return templates.TemplateResponse("_success.html", ctx)
    return RedirectResponse("/", status_code=303)


from .auth import create_session_cookie, require_admin


# Simple login form for admin (development). For production, use proper auth.
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_form(request: Request):
    return templates.TemplateResponse(
        "admin_login.html", {"request": request, "error": None}
    )


@app.post("/admin/login", response_class=HTMLResponse)
async def admin_login(
    request: Request, username: str = Form(...), password: str = Form(...)
):
    # Very simple: credentials stored in environment via settings
    if username == settings.ENV and password == settings.SECRET_KEY.get_secret_value():
        cookie = create_session_cookie({"user": username, "role": "admin"})
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie("session", cookie, httponly=True, samesite="lax")
        return response
    return templates.TemplateResponse(
        "admin_login.html", {"request": request, "error": "Invalid credentials"}
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_index(
    request: Request,
    session=Depends(require_admin),
    session_db: AsyncSession = Depends(get_session),
):
    # show list of contacts
    contacts = await list_contacts(session_db, limit=100)
    return templates.TemplateResponse(
        "admin_index.html", {"request": request, "contacts": contacts}
    )


@app.post("/admin/contact/delete", response_class=HTMLResponse)
async def admin_delete_contact(
    request: Request,
    id: int = Form(...),
    session=Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    # simple delete operation
    await db.execute(__import__("sqlmodel").sql.delete(Contact).where(Contact.id == id))
    await db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/admin/logout")
async def admin_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session")
    return response
