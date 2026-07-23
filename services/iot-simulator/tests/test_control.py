from __future__ import annotations

import asyncpg
import pytest
from jose import jwt

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
JWT_SECRET = "changeme_generate_a_real_secret_before_any_shared_deployment"


@pytest.fixture
async def auth_headers() -> dict:
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        row = await conn.fetchrow(
            "SELECT u.id, u.default_role_id FROM users u JOIN roles r ON r.id = u.default_role_id WHERE r.name = 'safety_officer' LIMIT 1"
        )
    finally:
        await conn.close()
    token = jwt.encode({"sub": str(row["id"]), "role_id": row["default_role_id"], "type": "access", "exp": 9999999999}, JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_world_and_control_require_authentication(client):
    assert client.get("/world").status_code == 401
    assert client.get("/status").status_code == 401
    assert client.post("/control/mode", json={"mode": "critical"}).status_code == 401
    assert client.post("/control/scenario", json={"scenario": "fire", "zone_id": "warehouse"}).status_code == 401
    assert client.post("/control/reset", json={}).status_code == 401


def test_get_world_topology(client, auth_headers):
    response = client.get("/world", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["zones"]) == 5
    assert len(body["workers"]) == 4
    assert len(body["buildings"]) == 4
    assert len(body["vehicles"]) == 3
    assert len(body["emergency_exits"]) == 7
    assert len(body["fire_systems"]) == 5
    assert len(body["pipelines"]) == 5
    assert len(body["robots"]) == 3
    assert len(body["emergency_responders"]) == 2
    tags = {eq["tag"] for zone in body["zones"] for eq in zone["equipment"]}
    assert "V-12" in tags  # DIGITAL_TWIN_EXPERIENCE.md's canonical predicted-leak valve
    assert all("building_id" in zone for zone in body["zones"])


def test_get_status_defaults_to_normal(client, auth_headers):
    response = client.get("/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["global_mode"] == "normal"
    assert body["active_scenarios"] == []


def test_set_global_mode(client, auth_headers):
    response = client.post("/control/mode", json={"mode": "critical"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["global_mode"] == "critical"

    status = client.get("/status", headers=auth_headers).json()
    assert status["global_mode"] == "critical"


def test_set_zone_mode(client, auth_headers):
    response = client.post("/control/mode", json={"mode": "warning", "zone_id": "boiler-room"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["zone_modes"] == {"boiler-room": "warning"}


def test_set_mode_unknown_zone_returns_404(client, auth_headers):
    response = client.post("/control/mode", json={"mode": "warning", "zone_id": "not-a-real-zone"}, headers=auth_headers)
    assert response.status_code == 404


def test_set_mode_invalid_mode_returns_422(client, auth_headers):
    response = client.post("/control/mode", json={"mode": "apocalyptic"}, headers=auth_headers)
    assert response.status_code == 422


def test_trigger_scenario_by_zone(client, auth_headers):
    response = client.post("/control/scenario", json={"scenario": "fire", "zone_id": "warehouse"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["scenario_type"] == "fire"
    assert body["zone_id"] == "warehouse"

    status = client.get("/status", headers=auth_headers).json()
    assert any(sc["scenario_type"] == "fire" and sc["zone_id"] == "warehouse" for sc in status["active_scenarios"])


def test_trigger_scenario_resolves_zone_from_equipment_id(client, auth_headers):
    response = client.post("/control/scenario", json={"scenario": "machine_failure", "equipment_id": "eq-c101"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["zone_id"] == "compressor-house"


def test_trigger_scenario_resolves_zone_from_worker_id(client, auth_headers):
    response = client.post("/control/scenario", json={"scenario": "worker_collapse", "worker_id": "w-2"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["zone_id"] == "boiler-room"


def test_trigger_machine_failure_without_equipment_id_returns_422(client, auth_headers):
    response = client.post("/control/scenario", json={"scenario": "machine_failure", "zone_id": "compressor-house"}, headers=auth_headers)
    assert response.status_code == 422


def test_trigger_scenario_with_no_target_returns_422(client, auth_headers):
    response = client.post("/control/scenario", json={"scenario": "fire"}, headers=auth_headers)
    assert response.status_code == 422


def test_trigger_scenario_unknown_equipment_returns_404(client, auth_headers):
    response = client.post("/control/scenario", json={"scenario": "machine_failure", "equipment_id": "eq-does-not-exist"}, headers=auth_headers)
    assert response.status_code == 404


def test_reset_all(client, auth_headers):
    client.post("/control/mode", json={"mode": "critical"}, headers=auth_headers)
    client.post("/control/scenario", json={"scenario": "fire", "zone_id": "warehouse"}, headers=auth_headers)

    response = client.post("/control/reset", json={}, headers=auth_headers)
    assert response.status_code == 200

    status = client.get("/status", headers=auth_headers).json()
    assert status["global_mode"] == "normal"
    assert status["active_scenarios"] == []


def test_reset_scoped_to_zone(client, auth_headers):
    client.post("/control/scenario", json={"scenario": "fire", "zone_id": "warehouse"}, headers=auth_headers)
    client.post("/control/scenario", json={"scenario": "fire", "zone_id": "tank-farm"}, headers=auth_headers)

    response = client.post("/control/reset", json={"zone_id": "warehouse"}, headers=auth_headers)
    assert response.status_code == 200

    status = client.get("/status", headers=auth_headers).json()
    zone_ids = {sc["zone_id"] for sc in status["active_scenarios"]}
    assert "warehouse" not in zone_ids
    assert "tank-farm" in zone_ids
