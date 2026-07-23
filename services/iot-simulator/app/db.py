"""
Async SQLAlchemy session factory -- added solely to back role-lookup queries
for `app/auth.py`. NullPool: this service's tests build several independent
TestClient(create_app()) instances in one file, and a real connection pool's
checked-out connections would outlive the event loop they were opened on.
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
