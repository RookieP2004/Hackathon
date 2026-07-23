from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aegis_api_common.testing import auth_header, mint_test_access_token
from aegis_db.models import Building, Employer, PermitType, Plant, Role, User, Worker, Zone
from app.config import get_settings
from app.db import get_db
from app.main import create_app

# See services/identity-rbac/tests/conftest.py for the full rationale behind
# this isolation strategy (function-scoped engine, real commits, unique
# per-test data — NOT transactional rollback, which was tried first and
# empirically broke asyncpg's single-operation-at-a-time constraint).
TEST_DATABASE_URL = "postgresql+asyncpg://aegis:changeme_local_only@localhost:5432/aegis_test"
TEST_DATABASE_URL_SYNC = "postgresql+psycopg2://aegis:changeme_local_only@localhost:5432/aegis_test"


@pytest.fixture(scope="session", autouse=True)
def _clean_test_tables():
    engine = create_engine(TEST_DATABASE_URL_SYNC)
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE users, permits, incident_timeline_events, incidents, reports, "
                "workers, employers, zones, buildings, plants RESTART IDENTITY CASCADE"
            )
        )
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
    return uuid.uuid4().hex[:10]


@pytest_asyncio.fixture
async def make_user(db_session, role_ids, settings, unique_suffix):
    counter = {"n": 0}

    async def _make(*, role: str) -> tuple[User, dict]:
        counter["n"] += 1
        user = User(
            email=f"test.{role}.{unique_suffix}.{counter['n']}@aegis-test.example",
            full_name=f"Test {role.replace('_', ' ').title()}",
            default_role_id=role_ids[role],
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


@pytest_asyncio.fixture
async def zone_id_factory(db_session, unique_suffix):
    """Creates a fresh Plant -> Building -> Zone chain, committed for real."""
    counter = {"n": 0}

    async def _make() -> int:
        counter["n"] += 1
        plant = Plant(code=f"TESTPLANT-{unique_suffix}-{counter['n']}", name="Test Plant", timezone="UTC")
        db_session.add(plant)
        await db_session.flush()

        building = Building(plant_id=plant.id, code="B1", name="Test Building")
        db_session.add(building)
        await db_session.flush()

        zone = Zone(building_id=building.id, code="Z1", name="Test Zone", zone_type="process_unit")
        db_session.add(zone)
        await db_session.commit()
        await db_session.refresh(zone)
        return zone.id

    return _make


@pytest_asyncio.fixture
async def plant_id_factory(db_session, unique_suffix):
    counter = {"n": 0}

    async def _make() -> int:
        counter["n"] += 1
        plant = Plant(code=f"TESTPLANT-P-{unique_suffix}-{counter['n']}", name="Test Plant", timezone="UTC")
        db_session.add(plant)
        await db_session.commit()
        await db_session.refresh(plant)
        return plant.id

    return _make


@pytest_asyncio.fixture
async def worker_id_factory(db_session, unique_suffix):
    counter = {"n": 0}

    async def _make() -> int:
        counter["n"] += 1
        employer = Employer(name=f"Test Employer {unique_suffix}-{counter['n']}", is_internal=True)
        db_session.add(employer)
        await db_session.flush()

        worker = Worker(
            employer_id=employer.id,
            badge_id=f"BADGE-{unique_suffix}-{counter['n']}",
            full_name="Test Worker",
            worker_type="employee",
        )
        db_session.add(worker)
        await db_session.commit()
        await db_session.refresh(worker)
        return worker.id

    return _make


@pytest_asyncio.fixture
async def permit_type_id_factory(db_session):
    async def _make(name: str = "Hot Work") -> int:
        result = await db_session.execute(select(PermitType).where(PermitType.name == name))
        existing = result.scalar_one_or_none()
        if existing:
            return existing.id
        pt = PermitType(name=name)
        db_session.add(pt)
        await db_session.commit()
        await db_session.refresh(pt)
        return pt.id

    return _make
