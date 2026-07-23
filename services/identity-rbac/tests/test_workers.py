from __future__ import annotations

import pytest
from sqlalchemy import select

from aegis_db.models import Employer


@pytest.fixture
def employer_id_factory(db_session):
    async def _make(name: str = "Test Employer") -> int:
        result = await db_session.execute(select(Employer).where(Employer.name == name))
        existing = result.scalar_one_or_none()
        if existing:
            return existing.id
        employer = Employer(name=name, is_internal=True)
        db_session.add(employer)
        # commit, not flush -- the app under test reads this employer through
        # a DIFFERENT session/connection (its own per-request session, per
        # conftest.py's isolation strategy), so a flush alone (visible only
        # within this fixture's own uncommitted transaction) is invisible to
        # it; confirmed by the ForeignKeyViolationError this produced before
        # being fixed to a real commit.
        await db_session.commit()
        await db_session.refresh(employer)
        return employer.id

    return _make


async def test_list_workers_requires_authentication(client):
    response = await client.get("/workers")
    assert response.status_code == 401


async def test_list_workers_readable_by_maintenance_engineer(client, make_user):
    _user, headers = await make_user(role="maintenance_engineer")
    response = await client.get("/workers", headers=headers)
    assert response.status_code == 200


async def test_list_workers_not_readable_by_viewer(client, make_user):
    """Viewer is intentionally NOT in the workers read-role list — a generic
    least-privilege role should not see personnel/badge data by default."""
    _user, headers = await make_user(role="viewer")
    response = await client.get("/workers", headers=headers)
    assert response.status_code == 403


async def test_create_worker_success(client, make_user, employer_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    employer_id = await employer_id_factory()

    response = await client.post(
        "/workers",
        headers=headers,
        json={"employer_id": employer_id, "badge_id": "BADGE-TEST-001", "full_name": "Test Worker"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["badge_id"] == "BADGE-TEST-001"
    assert body["active"] is True
    assert body["worker_type"] == "employee"


async def test_create_worker_duplicate_badge_conflicts(client, make_user, employer_id_factory):
    admin, headers = await make_user(role="system_admin")
    employer_id = await employer_id_factory()

    first = await client.post(
        "/workers",
        headers=headers,
        json={"employer_id": employer_id, "badge_id": "BADGE-DUP-001", "full_name": "First"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/workers",
        headers=headers,
        json={"employer_id": employer_id, "badge_id": "BADGE-DUP-001", "full_name": "Second"},
    )
    assert second.status_code == 409


async def test_create_worker_invalid_worker_type_returns_422(client, make_user, employer_id_factory):
    _admin, headers = await make_user(role="system_admin")
    employer_id = await employer_id_factory()

    response = await client.post(
        "/workers",
        headers=headers,
        json={
            "employer_id": employer_id,
            "badge_id": "BADGE-BAD-TYPE",
            "full_name": "Bad Type",
            "worker_type": "not_a_real_type",
        },
    )
    assert response.status_code == 422


async def test_deactivate_worker(client, make_user, employer_id_factory):
    admin, headers = await make_user(role="system_admin")
    employer_id = await employer_id_factory()

    create_resp = await client.post(
        "/workers",
        headers=headers,
        json={"employer_id": employer_id, "badge_id": "BADGE-DEACT-001", "full_name": "To Deactivate"},
    )
    worker_id = create_resp.json()["id"]

    response = await client.delete(f"/workers/{worker_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["active"] is False


async def test_filter_workers_by_employer(client, make_user, employer_id_factory):
    _admin, headers = await make_user(role="system_admin")
    employer_a = await employer_id_factory("Employer A")
    employer_b = await employer_id_factory("Employer B")

    await client.post(
        "/workers", headers=headers,
        json={"employer_id": employer_a, "badge_id": "BADGE-FILTER-A", "full_name": "Worker A"},
    )
    await client.post(
        "/workers", headers=headers,
        json={"employer_id": employer_b, "badge_id": "BADGE-FILTER-B", "full_name": "Worker B"},
    )

    response = await client.get(f"/workers?employer_id={employer_a}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(w["employer_id"] == employer_a for w in body["items"])
    assert any(w["badge_id"] == "BADGE-FILTER-A" for w in body["items"])
