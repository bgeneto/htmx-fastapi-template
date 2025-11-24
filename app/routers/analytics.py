from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..logger import get_logger
from ..models import Book, Car, Contact, User
from ..repository import get_session

router = APIRouter()
logger = get_logger("analytics")


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
