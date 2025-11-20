"""
Universal Data Grid Engine - Server-side pagination, filtering, and sorting

This module provides a generic, reusable grid system that introspects SQLModel tables
and automatically handles:
- Server-side pagination
- Dynamic filtering by any column
- Global search across specified fields
- Type-aware filtering (string ILIKE, numeric exact match)
- Sorting in both directions
"""

from typing import Generic, List, Optional, Type, TypeVar

from fastapi import Request
from pydantic import BaseModel
from sqlalchemy import asc, desc, func, inspect, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import String, Text
from sqlmodel import SQLModel, select

T = TypeVar("T", bound=SQLModel)


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model"""

    items: List[T]
    total: int
    page: int
    limit: int
    total_pages: int

    model_config = {"arbitrary_types_allowed": True}


class GridEngine:
    """
    Universal Data Grid Engine

    Usage:
        grid = GridEngine(session, Car)
        result = await grid.get_page(
            request=request,
            page=1,
            limit=10,
            sort_col="price",
            sort_dir="desc",
            search_fields=["make", "model", "version"]
        )
    """

    def __init__(self, session: AsyncSession, model: Type[T]):
        self.session = session
        self.model = model
        self.mapper = inspect(model)

    async def get_page(
        self,
        request: Request,
        page: int = 1,
        limit: int = 10,
        sort_col: str = "id",
        sort_dir: str = "asc",
        search_fields: Optional[List[str]] = None,
    ) -> PaginatedResponse[T]:
        """
        Get paginated, filtered, and sorted data from database

        Args:
            request: FastAPI Request object (for query params)
            page: Page number (1-indexed)
            limit: Items per page
            sort_col: Column name to sort by
            sort_dir: Sort direction ('asc' or 'desc')
            search_fields: List of field names to include in global search

        Returns:
            PaginatedResponse with items, pagination info, and metadata
        """
        if search_fields is None:
            search_fields = []

        # 1. Start with base query
        query = select(self.model)

        # 2. Global search (the 'q' param) - with partial matching (ILIKE)
        q = request.query_params.get("q", "").strip()
        if q and search_fields:
            conditions = []
            for field_name in search_fields:
                if hasattr(self.model, field_name):
                    col_attr = getattr(self.model, field_name)
                    col_type = col_attr.type

                    # Use ILIKE for string columns, cast to string for numbers
                    if isinstance(col_type, (String, Text)):
                        conditions.append(col_attr.ilike(f"%{q}%"))
                    else:
                        # For numeric/other fields, try exact match or fallback to string contains
                        try:
                            # For numeric fields, try to convert the search value
                            if hasattr(col_type, "python_type"):
                                python_type = col_type.python_type
                                if python_type:
                                    converted_value = python_type(q)
                                    conditions.append(col_attr == converted_value)
                                else:
                                    # Fallback to string search
                                    from sqlalchemy import Text as SQLText
                                    from sqlalchemy import cast

                                    conditions.append(
                                        cast(col_attr, SQLText).ilike(f"%{q}%")
                                    )
                            else:
                                # Type doesn't define python_type (like some custom types)
                                from sqlalchemy import Text as SQLText
                                from sqlalchemy import cast

                                conditions.append(
                                    cast(col_attr, SQLText).ilike(f"%{q}%")
                                )
                        except (
                            ValueError,
                            TypeError,
                            AttributeError,
                            NotImplementedError,
                        ):
                            # If any conversion fails, fallback to string-based search in the database
                            from sqlalchemy import Text as SQLText
                            from sqlalchemy import cast

                            conditions.append(cast(col_attr, SQLText).ilike(f"%{q}%"))

            if conditions:
                query = query.where(or_(*conditions))

        # 3. Dynamic column filtering (auto-inspection) - these work WITH search
        reserved = {"page", "limit", "q", "sort", "dir"}
        for key, value in request.query_params.items():
            if key not in reserved and value:
                if key in self.mapper.columns:
                    col_attr = getattr(self.model, key)
                    col_type = col_attr.type

                    # Always use partial matching for better UX
                    if isinstance(col_type, (String, Text)):
                        # String columns: ILIKE for partial matching
                        query = query.where(col_attr.ilike(f"%{value}%"))
                    else:
                        # For numeric fields, use string-based partial matching
                        # This allows "202" to match "2020", "2021", "2022" etc.
                        from sqlalchemy import Text as SQLText
                        from sqlalchemy import cast

                        query = query.where(cast(col_attr, SQLText).ilike(f"%{value}%"))

        # 4. Sorting (with fallback to primary key)
        if hasattr(self.model, sort_col) and sort_col in self.mapper.columns:
            col_attr = getattr(self.model, sort_col)
            if sort_dir == "desc":
                query = query.order_by(desc(col_attr))
            else:
                query = query.order_by(asc(col_attr))
        else:
            # Fallback to primary key
            pk_col = self.mapper.primary_key[0]
            query = query.order_by(desc(pk_col))

        # 5. Count total (optimized with subquery)
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # 6. Pagination (offset + limit)
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        items = result.scalars().all()

        # 7. Calculate metadata
        total_pages = (total + limit - 1) // limit

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )
