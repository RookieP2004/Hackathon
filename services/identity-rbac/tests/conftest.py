from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aegis_api_common.testing import auth_header, mint_test_access_token
from aegis_db.models import Role, User
from app.config import get_settings
from app.core.security import hash_password
from app.db import get_db
from app.main import create_app

# A dedicated database, never the seeded demo `aegis` database (libs/db/README.md).
#
# Isolation strategy: NOT per-test transaction rollback. That pattern (one
# shared connection + SAVEPOINTs across both the test's own setup code and
# the app's request handling) was tried first and rejected — confirmed
# empirically to raise `asyncpg.exceptions.InterfaceError: cannot perform
# operation: another operation is in progress`, because a single asyncpg
# connection is not safe for interleaved test-fixture-code + ASGI-request
# access. Instead: every test gets its own real session/connection, every
# write is a real commit, and every piece of test-generated data uses a
# random unique suffix so tests can never collide with each other's rows.
#
# The `engine` fixture below is function-scoped, not session-scoped — also
# confirmed empirically necessary: pytest-asyncio gives each test function
# its own event loop by default, and an asyncpg connection pool created in
# one loop breaks ("Event loop is closed") when reused from a different
# loop in a later test. A fresh engine per test avoids this entirely, at
# the cost of a small, acceptable per-test connection-setup overhead.
TEST_DATABASE_URL = "postgresql+asyncpg://aegis:changeme_local_only@localhost:5432/aegis_test"
TEST_DATABASE_URL_SYNC = "postgresql+psycopg2://aegis:changeme_local_only@localhost:5432/aegis_test"


@pytest.fixture(scope="session", autouse=True)
def _clean_test_tables():
    """
    Runs once per test session, entirely synchronously (a plain psycopg2
    connection, no event loop involved at all) — deliberately not an async
    fixture, so it can be session-scoped without the per-test-event-loop
    problem documented above affecting it.
    """
    engine = create_engine(TEST_DATABASE_URL_SYNC)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE users, workers, employers RESTART IDENTITY CASCADE"))
    engine.dispose()


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
def app(engine):
    application = create_app()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_db] = _override_get_db
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def role_ids(db_session) -> dict[str, int]:
    result = await db_session.execute(select(Role))
    return {r.name: r.id for r in result.scalars().all()}


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def unique_suffix() -> str:
    """A fresh per-test random suffix, so every test's generated emails/badge
    IDs/etc. are guaranteed unique without needing transactional rollback."""
    return uuid.uuid4().hex[:10]


@pytest_asyncio.fixture
async def make_user(db_session, role_ids, settings, unique_suffix):
    """
    Creates a real, committed User row for the given role name and returns
    (user, auth_headers) — RBAC checks the actual stored default_role_id on
    the users table, not anything in the JWT claims themselves, so a usable
    test principal requires a real row, not just a minted token (see
    app/domain/rbac.py's require_roles).
    """

    counter = {"n": 0}

    async def _make(*, role: str, email: str | None = None, password: str = "TestPassword123!") -> tuple[User, dict]:
        counter["n"] += 1
        user = User(
            email=email or f"test.{role}.{unique_suffix}.{counter['n']}@aegis-test.example",
            full_name=f"Test {role.replace('_', ' ').title()}",
            default_role_id=role_ids[role],
            password_hash=hash_password(password),
            status="active",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        token = mint_test_access_token(
            user_id=user.id, role_id=user.default_role_id,
            jwt_secret=settings.jwt_secret, jwt_algorithm=settings.jwt_algorithm,
        )
        return user, auth_header(token)

    return _make
