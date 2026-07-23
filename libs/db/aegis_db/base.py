"""
Declarative base + shared mixins for every model in aegis_db.

Table ownership per DATABASE_SCHEMA.md's per-service assignment (§4-§21) is
preserved as a comment on each model class, not enforced by separate Base
classes or separate metadata objects — this is ONE physical schema, per the
"one shared libs/db package" decision recorded in this package's README.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# A consistent naming convention for constraints/indexes is required for Alembic
# autogenerate to produce stable, diffable migrations across the whole schema.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # DATABASE_SCHEMA.md §0.4: "Timestamps: TIMESTAMPTZ always (never naive
    # TIMESTAMP)". Rather than relying on every model remembering to write
    # `DateTime(timezone=True)` explicitly, every bare `Mapped[datetime]`
    # annotation resolves to a timezone-aware column by default, system-wide,
    # from this one place. This was added after autogenerate revealed several
    # models had silently produced naive TIMESTAMP columns — a systemic fix,
    # not a per-column patch.
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


class TimestampMixin:
    """
    created_at/updated_at pair used by every mutable table in DATABASE_SCHEMA.md.
    The actual updated_at-on-UPDATE behavior is enforced by the set_updated_at()
    Postgres trigger (see alembic/versions/0001_extensions_and_functions.py) —
    the Python-side server_default/onupdate here is a client-side convenience
    for code that doesn't round-trip through Postgres (e.g. unit tests against
    an in-memory representation), not a substitute for the trigger.
    """

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
