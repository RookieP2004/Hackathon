"""
Exercises the real REST surface end to end, including the full lifespan
(sensor simulator load + FusionLoop startup) against the real `aegis`
database -- deliberately not using conftest.py's isolated `aegis_test`
fixtures, matching the precedent set by computer-vision's and rag-service's
own *_api.py integration tests.

One shared TestClient for the whole module, not one per test: this service's
lifespan starts a real background loop holding its own asyncpg connections
(FusionLoop) -- repeatedly starting and tearing down that lifespan across
many separate TestClient instances in quick succession (each with its own
anyio-managed event loop) left an orphaned asyncpg connection being closed
against a different, already-closed event loop than the one that opened it.
One shared app/client for the module sidesteps that entirely.
"""

import time

import asyncpg
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.config import get_settings
from app.main import create_app

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
V12_EQUIPMENT_ID = 2


async def _mint_token(role_name: str) -> str:
    settings = get_settings()
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        role_id = await conn.fetchval("SELECT id FROM roles WHERE name = $1", role_name)
    finally:
        await conn.close()
    payload = {"sub": "-1", "role_id": role_id, "type": "access", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture(scope="module")
def safety_officer_token():
    import asyncio

    return asyncio.run(_mint_token("safety_officer"))


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(safety_officer_token):
    return {"Authorization": f"Bearer {safety_officer_token}"}


def test_hazards_endpoint(client, auth_headers):
    response = client.get("/fusion/hazards", headers=auth_headers)
    assert response.status_code == 200
    names = {h["name"] for h in response.json()["hazard_classes"]}
    assert names == {"fire", "explosion", "gas_leak", "worker_injury", "machine_failure"}


def test_simulator_status_reflects_loaded_sensors(client, auth_headers):
    response = client.get("/fusion/simulator/status", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["sensors_loaded"] > 0


def test_assess_endpoint_returns_five_bundles(client, auth_headers):
    response = client.post(f"/fusion/assess/{V12_EQUIPMENT_ID}", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["assessments"]) == 5


def test_assess_unknown_equipment_returns_404(client, auth_headers):
    response = client.post("/fusion/assess/999999", headers=auth_headers)
    assert response.status_code == 404


def test_scenario_injection_and_reset(client, auth_headers):
    response = client.post(
        "/fusion/simulator/scenario", json={"sensor_id": 1, "target_value": 3000.0, "rate": 0.3}, headers=auth_headers,
    )
    assert response.status_code == 200
    reset_response = client.post("/fusion/simulator/reset", headers=auth_headers)
    assert reset_response.status_code == 200


def test_fusion_endpoints_require_authentication(client):
    response = client.get("/fusion/hazards")
    assert response.status_code == 401
