"""
Shared filtering. Each endpoint defines its own Pydantic filter schema (a
model of Optional fields matching what that resource actually lets you filter
by — deliberately NOT a fully generic "filter by any field" system, which
would make it trivial to accidentally expose a field that shouldn't be
filterable, e.g. a password hash). apply_filters() takes that validated
Pydantic object and builds the SQLAlchemy WHERE clauses from it.

Operator suffixes on a filter field's name follow the widely-understood
Django-style convention: `_gte`, `_lte`, `_in`, `_ilike`. Because the base
field name (before the suffix) is always resolved via `getattr(model, ...)`
and will raise AttributeError (caught and turned into a 500-with-log, not a
silent no-op) if it doesn't exist on the model, there is no path from a
filter schema field to an arbitrary/unintended column — the filter schema
itself is the allow-list.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select

_OPERATOR_SUFFIXES = ("_gte", "_lte", "_gt", "_lt", "_in", "_ilike")


def apply_filters(query: Select, model: type, filters: Any) -> Select:
    """`filters` is a Pydantic model instance; unset/None fields are skipped."""
    data = filters.model_dump(exclude_unset=True, exclude_none=True)

    for key, value in data.items():
        field_name = key
        operator = None
        for suffix in _OPERATOR_SUFFIXES:
            if key.endswith(suffix):
                field_name = key[: -len(suffix)]
                operator = suffix
                break

        column = getattr(model, field_name)  # AttributeError -> 500 if the filter schema is wrong, by design

        if operator == "_gte":
            query = query.where(column >= value)
        elif operator == "_lte":
            query = query.where(column <= value)
        elif operator == "_gt":
            query = query.where(column > value)
        elif operator == "_lt":
            query = query.where(column < value)
        elif operator == "_in":
            query = query.where(column.in_(value))
        elif operator == "_ilike":
            query = query.where(column.ilike(f"%{value}%"))
        else:
            query = query.where(column == value)

    return query
