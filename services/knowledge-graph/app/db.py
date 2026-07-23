"""
Async SQLAlchemy session factory -- added solely to back role-lookup queries
for `app/auth.py` (aegis_api_common.AuthDependencies.require_roles reads
Role/UserRoleScope from Postgres). This service still owns no relational
tables/migrations of its own; Neo4j remains the primary store and Postgres
sync elsewhere in this service still uses raw asyncpg (sync.py's docstring).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

# NullPool, not the default pooled engine: this module-level engine is a
# singleton for this service's process lifetime, but this service's tests
# construct several independent `TestClient(create_app())` instances (each
# with its own event loop) in one file -- a real connection pool's checked-
# out connections would outlive the loop they were opened on and fail on the
# next test with "Event loop is closed". Role lookups are infrequent enough
# that paying a fresh-connection cost per request is a non-issue.
engine = create_async_engine(settings.database_url, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
