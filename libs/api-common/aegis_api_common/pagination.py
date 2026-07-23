"""
Shared pagination — every list endpoint across all 15 modules uses this same
shape, so a frontend client written against one module's list response works
identically against every other module's.
"""

from __future__ import annotations

import math
from typing import Callable, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class PaginationParams:
    """
    `Depends(PaginationParams)` — page is 1-indexed (not 0-indexed) to match
    what a human types into a UI pager, page_size is capped at 100 to prevent
    a single request from forcing an unbounded table scan/response payload.
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="1-indexed page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page, max 100"),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(description="Total items matching the query, across all pages")
    page: int
    page_size: int
    total_pages: int


async def paginate(
    session: AsyncSession,
    query: Select,
    params: PaginationParams,
    schema: type[T],
    transform: Callable[[object], object] | None = None,
) -> Page[T]:
    """
    Runs a COUNT(*) over the unpaginated query and a LIMIT/OFFSET page fetch
    as two queries -- a single query with a window function COUNT(*) OVER()
    would save a round trip, but at the row counts this system's list
    endpoints deal with (dozens to low thousands per resource, never a raw
    high-frequency hypertable — see DATABASE_SCHEMA.md §0.5's regime split),
    the extra round trip is not the bottleneck worth optimizing for; the
    two-query form is far easier to read and reason about correctness for.

    `transform`, if given, is applied to each ORM row before schema
    validation — for the common case (one query, one model, matching
    response schema) it's unnecessary; it exists for modules whose read
    schema is assembled from a join or a supertype/subtype pair (e.g. the
    Machines module's Equipment+Machine combination, DATABASE_SCHEMA.md
    §5.2) where a flat `schema.model_validate(row)` can't see the joined
    table's columns at all.
    """
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    paged_query = query.offset(params.offset).limit(params.page_size)
    rows = (await session.execute(paged_query)).scalars().all()

    items = [schema.model_validate(transform(row) if transform else row) for row in rows]
    total_pages = math.ceil(total / params.page_size) if total > 0 else 0

    return Page[schema](  # type: ignore[valid-type]
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
    )
