from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..grid_engine import GridEngine, PaginatedResponse
from ..i18n import gettext as _
from ..logger import get_logger
from ..models import Car, CarBase, User
from ..repository import get_session
from ..templates import templates
from ..users import current_user_optional

router = APIRouter()
logger = get_logger("cars")


@router.get("/cars", response_class=HTMLResponse)
async def cars_page(
    request: Request,
    user: Optional[User] = Depends(current_user_optional),
    session: AsyncSession = Depends(get_session),
):
    """Display cars page with universal data grid - publicly accessible"""
    return templates.TemplateResponse(
        "pages/cars.html",
        {
            "request": request,
            "user": user,
            "api_url": "/api/cars",
            "columns": [
                {"key": "id", "label": _("ID"), "width": 70, "sortable": True},
                {
                    "key": "make",
                    "label": _("Make"),
                    "width": 120,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "model",
                    "label": _("Model"),
                    "width": 150,
                    "sortable": True,
                    "filterable": True,
                },
                {
                    "key": "version",
                    "label": _("Version"),
                    "width": 150,
                    "sortable": True,
                    "filterable": True,
                },
                {"key": "year", "label": _("Year"), "width": 80, "sortable": True},
                {
                    "key": "price",
                    "label": _("Price"),
                    "width": 100,
                    "sortable": True,
                },
                {
                    "key": "created_at",
                    "label": _("Created"),
                    "width": 180,
                    "sortable": True,
                },
            ],
        },
    )


@router.get("/api/cars", response_model=PaginatedResponse[Car])
async def get_cars_grid(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "id",
    dir: str = "asc",
    session: AsyncSession = Depends(get_session),
):
    """API endpoint for cars grid - publicly accessible"""
    grid = GridEngine(session, Car)
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["make", "model", "version", "year", "price"],
    )


@router.post("/api/cars", response_model=Car)
async def create_car(
    car_data: CarBase,
    session: AsyncSession = Depends(get_session),
):
    """Create a new car - publicly accessible"""
    logger.info(f"Creating car with data: {car_data}")

    # Create Car instance from validated CarBase data
    car = Car(**car_data.model_dump())
    session.add(car)
    await session.commit()
    await session.refresh(car)
    return car


@router.put("/api/cars/{car_id}", response_model=Car)
async def update_car(
    car_id: int,
    car_data: CarBase,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing car - publicly accessible"""
    result = await session.execute(select(Car).where(Car.id == car_id))
    car = result.scalar_one_or_none()

    if not car:
        raise HTTPException(status_code=404, detail="Car not found")

    # Only update fields that were provided (exclude_unset=True)
    update_data = car_data.model_dump(exclude_unset=True)
    protected_fields = {"id", "created_at"}

    for key, value in update_data.items():
        if key not in protected_fields and hasattr(car, key):
            setattr(car, key, value)

    await session.commit()
    await session.refresh(car)
    return car


@router.delete("/api/cars/{car_id}")
async def delete_car(
    car_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a car"""
    # First check if the car exists
    result = await session.execute(select(Car).where(Car.id == car_id))
    car = result.scalar_one_or_none()

    if not car:
        raise HTTPException(status_code=404, detail="Car not found")

    try:
        # Use raw SQL delete with proper SQLAlchemy import
        from sqlalchemy import delete

        await session.execute(delete(Car).where(Car.id == car_id))  # type: ignore[arg-type]
        await session.commit()

        # Verify deletion by checking if car still exists
        verify_result = await session.execute(select(Car).where(Car.id == car_id))
        if verify_result.scalar_one_or_none() is not None:
            await session.rollback()
            raise HTTPException(
                status_code=500, detail="Failed to delete car from database"
            )

        logger.info(
            f"Successfully deleted car ID {car_id}: {car.make} {car.model} ({car.year})"
        )
        return {"success": True, "message": "Car deleted successfully"}

    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete car ID {car_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete car: {str(e)}")
