"""
Async SQLAlchemy session factory, shared by every route in this service.

NullPool, not a real connection pool: this service's tests construct several
independent `TestClient(create_app())` instances in one file (each with its
own event loop), and a real pool's checked-out connections would outlive the
loop they were opened on ("Event loop is closed" on the next test). This
service's own DB usage is limited to auth role lookups, not a hot path, so
paying a fresh-connection cost per request is a non-issue.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
