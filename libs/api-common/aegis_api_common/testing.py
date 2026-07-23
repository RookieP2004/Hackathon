"""
Shared test helpers. Not fixtures themselves (pytest fixtures must live in
each service's own conftest.py to be discovered), but the building blocks
every service's conftest.py composes into fixtures — so "mint a valid test
token", "build an authorization header", and "run this test in an isolated,
auto-rolled-back transaction against the real database" are implemented
once, not 8 times with 8 chances to drift apart.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

from jose import jwt
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker


def mint_test_access_token(
    *,
    user_id: int,
    role_id: int,
    jwt_secret: str,
    jwt_algorithm: str = "HS256",
    expires_minutes: int = 15,
) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "role_id": role_id,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "type": "access",
    }
    return jwt.encode(claims, jwt_secret, algorithm=jwt_algorithm)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def transactional_session(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """
    Standard SQLAlchemy transactional-test pattern, adapted for async: an
    outer transaction is opened on `connection` by the caller (see each
    service's conftest.py), a Session is bound to that same connection with
    `join_transaction_mode="create_savepoint"` so any `session.commit()` the
    code under test calls only releases a savepoint rather than the real
    transaction, and the caller's outer-transaction rollback (after the test
    completes) undoes everything -- including committed writes -- with zero
    special-casing needed in the application code being tested. This is what
    lets every module's test suite run against the actual live Postgres
    instance (not sqlite, not a mock) while staying fully isolated per test.
    """
    session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
