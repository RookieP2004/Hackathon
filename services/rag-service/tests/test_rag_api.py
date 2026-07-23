"""
Exercises the real REST surface end to end, including the full lifespan
(model warm-up, feedback-table creation, initial index build) against the
real `aegis` database -- deliberately NOT using conftest.py's `app`/`client`
fixtures (those point at the isolated `aegis_test` database for the
knowledge-base CRUD tests), since this file's purpose is to verify the
actual production wiring, the same way computer-vision's test_vision_api.py
did for its service.
"""

import time
from datetime import date

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


@pytest.fixture(scope="module", autouse=True)
def _seed_and_cleanup_api_test_doc():
    async def _seed():
        conn = await asyncpg.connect(POSTGRES_DSN)
        try:
            await conn.execute("DELETE FROM knowledge_documents WHERE title LIKE 'ZZAPITEST-%'")
            await conn.execute(
                "INSERT INTO knowledge_documents (title, document_class, authority, content, version, effective_date) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                "ZZAPITEST-OISD Clause 9.9", "oisd", "regulatory",
                "Clause 9.9: Test clause\nThe test threshold for this API check is set at 42 percent LEL.",
                "1", date(2024, 1, 1),
            )
        finally:
            await conn.close()

    async def _cleanup():
        conn = await asyncpg.connect(POSTGRES_DSN)
        try:
            await conn.execute("DELETE FROM knowledge_documents WHERE title LIKE 'ZZAPITEST-%'")
            await conn.execute("DELETE FROM rag_feedback WHERE query_text LIKE 'zzapitest%'")
        finally:
            await conn.close()

    import asyncio

    asyncio.run(_seed())
    yield
    asyncio.run(_cleanup())


def test_reindex_query_and_feedback_end_to_end(safety_officer_token):
    headers = {"Authorization": f"Bearer {safety_officer_token}"}
    with TestClient(create_app()) as client:
        reindex_response = client.post("/rag/reindex", headers=headers)
        assert reindex_response.status_code == 200
        assert reindex_response.json()["chunks_indexed"] > 0

        query_response = client.post(
            "/rag/query",
            json={"query": "zzapitest what is the test threshold for this clause"},
            headers=headers,
        )
        assert query_response.status_code == 200
        body = query_response.json()
        assert body["refused"] is False
        citations = [c["citation"] for c in body["chunks"]]
        assert any("ZZAPITEST-OISD Clause 9.9" in c for c in citations)

        chunk_id = body["chunks"][0]["chunk_id"]
        feedback_response = client.post(
            "/rag/feedback",
            json={"query": "zzapitest what is the test threshold for this clause", "chunk_id": chunk_id, "signal": "positive"},
            headers=headers,
        )
        assert feedback_response.status_code == 201


def test_query_requires_authentication():
    with TestClient(create_app()) as client:
        response = client.post("/rag/query", json={"query": "anything"})
        assert response.status_code == 401
