from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..grid_engine import GridEngine, PaginatedResponse
from ..i18n import gettext as _
from ..logger import get_logger
from ..models import Book, BookBase, User
from ..repository import get_session
from ..templates import templates
from ..users import current_user_optional

router = APIRouter()
logger = get_logger("books")


@router.get("/books", response_class=HTMLResponse)
async def books_page(
    request: Request,
    user: Optional[User] = Depends(current_user_optional),
):
    """Display books page with universal data grid"""
    return templates.TemplateResponse(
        "pages/books.html",
        {
            "request": request,
            "user": user,
            "api_url": "/api/books",
            # Note: We don't strictly need to pass columns here if the frontend
            # could also auto-detect, but for now we define frontend columns manually.
            # The backend GridEngine WILL auto-detect search fields.
            "columns": [
                {"key": "id", "label": _("ID"), "width": 70, "sortable": True},
                {
                    "key": "title",
                    "label": _("Title"),
                    "width": 250,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "author",
                    "label": _("Author"),
                    "width": 200,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "isbn",
                    "label": _("ISBN"),
                    "width": 150,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "published_year",
                    "label": _("Year"),
                    "width": 100,
                    "sortable": True,
                },
                {
                    "key": "price",
                    "label": _("Price"),
                    "width": 100,
                    "sortable": True,
                },
                {"key": "pages", "label": _("Pages"), "width": 100, "sortable": True},
                {
                    "key": "summary",
                    "label": _("Summary"),
                    "width": 300,
                    "sortable": False,
                },
            ],
        },
    )


@router.get("/api/books", response_model=PaginatedResponse[Book])
async def get_books_grid(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "id",
    dir: str = "asc",
    session: AsyncSession = Depends(get_session),
):
    """API endpoint for books grid - demonstrating auto-detection of search fields"""
    grid = GridEngine(session, Book)
    # Note: We do NOT pass search_fields here to test auto-detection!
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
    )


@router.post("/api/books", response_model=Book)
async def create_book(
    book_data: BookBase,
    session: AsyncSession = Depends(get_session),
):
    """Create a new book with validation via BookBase"""
    logger.info(f"Creating book with data: {book_data}")

    # Create Book instance from validated BookBase data
    book = Book(**book_data.model_dump())
    session.add(book)
    await session.commit()
    await session.refresh(book)
    return book


@router.put("/api/books/{book_id}", response_model=Book)
async def update_book(
    book_id: int,
    book_data: BookBase,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing book with validation via BookBase"""
    result = await session.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Only update fields that were provided (exclude_unset=True)
    update_data = book_data.model_dump(exclude_unset=True)
    protected_fields = {"id", "created_at"}

    for key, value in update_data.items():
        if key not in protected_fields and hasattr(book, key):
            setattr(book, key, value)

    await session.commit()
    await session.refresh(book)
    return book


@router.delete("/api/books/{book_id}")
async def delete_book(
    book_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a book"""
    result = await session.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    await session.delete(book)
    await session.commit()
    return {"success": True, "message": "Book deleted successfully"}
