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


# Strategy classes for different filter types
class SearchFilterStrategy:
    """Handles global search across specified fields"""

    def __init__(self, search_fields: List[str], search_query: str):
        self.search_fields = search_fields
        self.search_query = search_query.strip()

    def apply(self, query, model, mapper):
        if not self.search_query or not self.search_fields:
            return query

        conditions = []
        for field_name in self.search_fields:
            if hasattr(model, field_name):
                col_attr = getattr(model, field_name)
                condition = self._create_search_condition(col_attr)
                if condition:
                    conditions.append(condition)

        if conditions:
            query = query.where(or_(*conditions))

        return query

    def _create_search_condition(self, col_attr):
        col_type = col_attr.type

        if isinstance(col_type, (String, Text)):
            return col_attr.ilike(f"%{self.search_query}%")

        # For numeric/other fields, try exact match or fallback to string contains
        try:
            if hasattr(col_type, "python_type"):
                python_type = col_type.python_type
                if python_type:
                    converted_value = python_type(self.search_query)
                    return col_attr == converted_value
        except (ValueError, TypeError, AttributeError, NotImplementedError):
            pass

        # Fallback to string-based search
        from sqlalchemy import Text as SQLText
        from sqlalchemy import cast

        return cast(col_attr, SQLText).ilike(f"%{self.search_query}%")


class ColumnFilterStrategy:
    """Handles dynamic column filtering from query parameters"""

    def __init__(self, request: Request):
        self.request = request
        self.reserved_params = {"page", "limit", "q", "sort", "dir"}

    def apply(self, query, model, mapper):
        for key, value in self.request.query_params.items():
            if key not in self.reserved_params and value and key in mapper.columns:
                col_attr = getattr(model, key)
                query = self._apply_column_filter(query, col_attr, value)

        return query

    def _apply_column_filter(self, query, col_attr, value):
        col_type = col_attr.type

        # Always use partial matching for better UX
        if isinstance(col_type, (String, Text)):
            return query.where(col_attr.ilike(f"%{value}%"))
        else:
            # For numeric fields, use string-based partial matching
            from sqlalchemy import Text as SQLText
            from sqlalchemy import cast

            return query.where(cast(col_attr, SQLText).ilike(f"%{value}%"))


class SortingStrategy:
    """Handles query sorting with fallback to primary key"""

    def __init__(self, sort_col: str, sort_dir: str = "asc"):
        self.sort_col = sort_col
        self.sort_dir = sort_dir.lower()

    def apply(self, query, model, mapper):
        if hasattr(model, self.sort_col) and self.sort_col in mapper.columns:
            col_attr = getattr(model, self.sort_col)
        else:
            # Fallback to primary key
            col_attr = mapper.primary_key[0]

        if self.sort_dir == "desc":
            return query.order_by(desc(col_attr))
        else:
            return query.order_by(asc(col_attr))


class QueryBuilder:
    """Builder pattern for constructing complex queries"""

    def __init__(self, model: Type[T]):
        self.query = select(model)
        self.model = model
        self.mapper = inspect(model)

    def apply_filters(self, strategy):
        self.query = strategy.apply(self.query, self.model, self.mapper)
        return self

    def apply_sorting(self, strategy):
        self.query = strategy.apply(self.query, self.model, self.mapper)
        return self

    async def execute_paginated(self, session: AsyncSession, page: int, limit: int):
        # Count total (optimized with subquery)
        count_query = select(func.count()).select_from(self.query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar_one()

        # Pagination (offset + limit)
        offset = (page - 1) * limit
        query = self.query.offset(offset).limit(limit)
        result = await session.execute(query)
        items = result.scalars().all()

        # Calculate metadata
        total_pages = (total + limit - 1) // limit

        return PaginatedResponse[T](
            items=list(items),
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )


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

        # Build query using strategy pattern
        query_builder = QueryBuilder(self.model)

        # Apply filters using strategy pattern
        search_strategy = SearchFilterStrategy(
            search_fields, request.query_params.get("q", "")
        )
        query_builder.apply_filters(search_strategy)

        column_filter_strategy = ColumnFilterStrategy(request)
        query_builder.apply_filters(column_filter_strategy)

        # Apply sorting
        sorting_strategy = SortingStrategy(sort_col, sort_dir)
        query_builder.apply_sorting(sorting_strategy)

        # Execute and return paginated results
        return await query_builder.execute_paginated(self.session, page, limit)
