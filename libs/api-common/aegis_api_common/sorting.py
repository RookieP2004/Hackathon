"""
Shared sorting — a single `sort` query param string (`-created_at` for
descending, `name` for ascending, comma-separated for multi-field), validated
against an explicit per-endpoint allow-list before ever touching a SQLAlchemy
column reference. The allow-list is the actual security control here: without
it, a client-supplied field name could be used to sort by (and therefore probe
the existence/ordering of) a column the endpoint never intended to expose.
"""

from __future__ import annotations

from fastapi import HTTPException, Query, status
from sqlalchemy import Select


def parse_sort(
    sort: str | None = Query(
        None,
        description="Comma-separated fields, prefix with '-' for descending, e.g. '-created_at,name'",
    ),
) -> list[tuple[str, bool]]:
    """Returns [(field_name, descending), ...]. Empty list means 'no sort requested'."""
    if not sort:
        return []
    parsed = []
    for raw_field in sort.split(","):
        raw_field = raw_field.strip()
        if not raw_field:
            continue
        descending = raw_field.startswith("-")
        field = raw_field[1:] if descending else raw_field
        parsed.append((field, descending))
    return parsed


def apply_sorting(
    query: Select,
    model: type,
    sort_fields: list[tuple[str, bool]],
    allowed_fields: set[str],
    default_field: str = "id",
) -> Select:
    if not sort_fields:
        column = getattr(model, default_field)
        return query.order_by(column.asc())

    for field, descending in sort_fields:
        if field not in allowed_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot sort by '{field}'. Allowed fields: {', '.join(sorted(allowed_fields))}",
            )
        column = getattr(model, field)
        query = query.order_by(column.desc() if descending else column.asc())

    return query
