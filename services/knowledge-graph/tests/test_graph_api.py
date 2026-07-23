import asyncpg
from fastapi.testclient import TestClient
from jose import jwt

from app.main import create_app

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
JWT_SECRET = "changeme_generate_a_real_secret_before_any_shared_deployment"


async def _auth_headers() -> dict:
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        row = await conn.fetchrow(
            "SELECT u.id, u.default_role_id FROM users u JOIN roles r ON r.id = u.default_role_id WHERE r.name = 'safety_officer' LIMIT 1"
        )
    finally:
        await conn.close()
    token = jwt.encode({"sub": str(row["id"]), "role_id": row["default_role_id"], "type": "access", "exp": 9999999999}, JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


async def test_sync_and_read_endpoints_work_end_to_end():
    headers = await _auth_headers()
    with TestClient(create_app()) as client:
        sync_response = client.post("/graph/sync", headers=headers)
        assert sync_response.status_code == 200
        counts = sync_response.json()
        assert counts["zones"] > 0
        assert counts["equipment"] > 0

        # Pick a real equipment tag that should now exist post-sync.
        cypher_response = client.post(
            "/graph/cypher/query",
            json={"query": "MATCH (n:Equipment) RETURN n.tag AS tag LIMIT 1", "params": {}},
            headers=headers,
        )
        assert cypher_response.status_code == 200
        results = cypher_response.json()["results"]
        assert len(results) == 1
        tag = results[0]["tag"]

        downstream_response = client.get(f"/graph/equipment/{tag}/downstream", headers=headers)
        assert downstream_response.status_code == 200
        assert "downstream" in downstream_response.json()


async def test_cypher_query_rejects_write_clauses():
    headers = await _auth_headers()
    with TestClient(create_app()) as client:
        response = client.post(
            "/graph/cypher/query",
            json={"query": "MATCH (n:Equipment) DETACH DELETE n", "params": {}},
            headers=headers,
        )
        assert response.status_code == 422


async def test_cypher_query_rejects_apoc_procedure_calls_bare_call_not_just_call_brace():
    """Regression test for the real bypass found in this audit: the blocklist
    used to only catch "CALL {" (subquery form), not a bare "CALL" -- so
    "CALL apoc.merge.node(...)" (a genuine write, via the APOC plugin this
    Neo4j container loads) contained none of the blocked keywords and would
    have executed through this "read-only" endpoint."""
    headers = await _auth_headers()
    with TestClient(create_app()) as client:
        response = client.post(
            "/graph/cypher/query",
            json={"query": "CALL apoc.create.node(['Malicious'], {}) YIELD node RETURN node", "params": {}},
            headers=headers,
        )
        assert response.status_code == 422


async def test_graph_endpoints_require_authentication():
    with TestClient(create_app()) as client:
        assert client.post("/graph/sync").status_code == 401
        assert client.post("/graph/cypher/query", json={"query": "MATCH (n) RETURN n LIMIT 1"}).status_code == 401
        assert client.get("/graph/equipment/1/risk-context").status_code == 401


async def test_sync_one_permit_incrementally_without_a_full_resync():
    headers = await _auth_headers()
    with TestClient(create_app()) as client:
        # permit id 1 is a real, seeded permit (HW-2026-0001) -- sync it in
        # first via the full pull so its Worker/Zone/Equipment neighbors exist,
        # then confirm the single-permit sync updates its own node correctly.
        client.post("/graph/sync", headers=headers)

        response = client.post("/graph/permits/1/sync", headers=headers)
        assert response.status_code == 200
        assert response.json()["synced_permit_id"] == 1

        check = client.post(
            "/graph/cypher/query",
            json={"query": "MATCH (n:Permit {id: $id}) RETURN n.permitNumber AS permitNumber, n.status AS status", "params": {"id": 1}},
            headers=headers,
        )
        results = check.json()["results"]
        assert len(results) == 1
        assert results[0]["permitNumber"] == "HW-2026-0001"


async def test_sync_one_permit_404s_for_an_unknown_permit():
    headers = await _auth_headers()
    with TestClient(create_app()) as client:
        response = client.post("/graph/permits/999999999/sync", headers=headers)
        assert response.status_code == 404


async def test_risk_write_endpoint():
    headers = await _auth_headers()
    with TestClient(create_app()) as client:
        response = client.post(
            "/graph/risk",
            json={
                "id": "test-api-risk-1",
                "hazard_class": "test_hazard",
                "score": 88.0,
                "confidence": 0.85,
                "assessed_at": "2026-07-22T00:00:00+00:00",
                "gate_structure_version": "test-v1",
            },
            headers=headers,
        )
        assert response.status_code == 201

        check = client.post(
            "/graph/cypher/query",
            json={"query": "MATCH (n:Risk {id: $id}) RETURN n.hazardClass AS hazardClass", "params": {"id": "test-api-risk-1"}},
            headers=headers,
        )
        assert check.json()["results"][0]["hazardClass"] == "test_hazard"
