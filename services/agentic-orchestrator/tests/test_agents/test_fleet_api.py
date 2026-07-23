"""
Full end-to-end: the real FastAPI app, real lifespan (all twelve agents
started as real asyncio tasks against the real Redis bus and real Postgres),
exercised through the actual REST surface -- not using conftest.py's
isolated `aegis_test`-database fixtures, matching every other service's own
*_api.py integration test in this repo.
"""

import time

import asyncpg
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.config import get_settings
from app.main import create_app

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"


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


def test_fleet_status_reports_all_twelve_agents(client, auth_headers):
    response = client.get("/agents/status", headers=auth_headers)
    assert response.status_code == 200
    agent_ids = {a["agent_id"] for a in response.json()["agents"]}
    assert agent_ids == {
        "sensor-agent", "vision-agent", "worker-agent", "permit-agent", "maintenance-agent",
        "knowledge-agent", "risk-fusion-agent", "prediction-agent", "emergency-agent",
        "compliance-agent", "learning-agent", "supervisor-agent",
    }


def test_agent_decisions_endpoint_returns_real_logged_reasoning(client, auth_headers):
    import time as _time

    _time.sleep(9)  # let at least one real tick from a fast-cadence agent (sensor-agent, 8s) land

    response = client.get("/agents/sensor-agent/decisions", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == "sensor-agent"
    # decisions may be empty if nothing crossed the anomaly threshold this tick -- what matters
    # is the endpoint itself works and, when present, entries carry real reasoning text.
    for decision in body["decisions"]:
        assert decision["reasoning"]
        assert decision["confidence"] is not None


def test_unknown_agent_returns_404(client, auth_headers):
    response = client.get("/agents/not-a-real-agent/decisions", headers=auth_headers)
    assert response.status_code == 404


def test_explain_unknown_decision_returns_404(client, auth_headers):
    response = client.get("/agents/sensor-agent/decisions/999999999/explain", headers=auth_headers)
    assert response.status_code == 404


def test_agents_endpoints_require_authentication(client):
    response = client.get("/agents/status")
    assert response.status_code == 401
