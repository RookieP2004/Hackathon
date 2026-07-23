"""
Full end-to-end integration: real Postgres rows -> real chunking -> real
embeddings -> real hybrid search -> real cross-encoder re-rank -> real
hallucination-gating, run against the actual running Postgres database (the
same one every other service in this repo uses). Seeded rows use a
`ZZTEST-` title prefix and are deleted before and after this module runs, so
this never pollutes or depends on the real corpus scripts/seed_corpus.py
populates.
"""

from datetime import date, datetime, timedelta, timezone

import asyncpg
import pytest
from aegis_api_common import ServiceActorTokenMinter

from app.rag.indexing import build_chunks_from_postgres
from app.rag.pipeline import query_knowledge_base
from app.rag.store import ChunkIndex, ensure_feedback_tables, record_feedback

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
KNOWLEDGE_GRAPH_URL = "http://localhost:8007"
TOKEN_MINTER = ServiceActorTokenMinter(
    postgres_dsn=POSTGRES_DSN, jwt_secret="changeme_generate_a_real_secret_before_any_shared_deployment", jwt_algorithm="HS256",
)

TEST_DOCS = [
    {
        "title": "ZZTEST-OISD Clause 4.3",
        "document_class": "oisd",
        "authority": "regulatory",
        "content": "Clause 4.3: Inspection interval\nFixed fire suppression systems shall be inspected at intervals not exceeding 180 days.",
        "version": "3",
        "effective_date": date(2021, 6, 1),
        "superseded_at": None,
    },
    {
        "title": "ZZTEST-Old SOP Version",
        "document_class": "safety_sop",
        "authority": "internal",
        "content": "Step 1: An outdated isolation procedure that has since been superseded.",
        "version": "1",
        "effective_date": date(2020, 1, 1),
        "superseded_at": datetime.now(timezone.utc) - timedelta(days=10),
    },
    {
        "title": "ZZTEST-Audit AUD-001",
        "document_class": "audit_report",
        "authority": "internal",
        "content": "Finding 1: A restricted-access audit finding about valve seal inspection compliance.",
        "version": "1",
        "effective_date": date(2026, 1, 1),
        "superseded_at": None,
    },
]


@pytest.fixture
async def seeded_index():
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await conn.execute("DELETE FROM knowledge_documents WHERE title LIKE 'ZZTEST-%'")
        ids = []
        for doc in TEST_DOCS:
            row_id = await conn.fetchval(
                "INSERT INTO knowledge_documents (title, document_class, authority, content, version, effective_date, superseded_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
                doc["title"], doc["document_class"], doc["authority"], doc["content"],
                doc["version"], doc["effective_date"], doc["superseded_at"],
            )
            ids.append(row_id)
    finally:
        await conn.close()

    await ensure_feedback_tables(POSTGRES_DSN)
    index = ChunkIndex()
    chunks = await build_chunks_from_postgres(POSTGRES_DSN)
    index.rebuild(chunks)

    yield index

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await conn.execute("DELETE FROM knowledge_documents WHERE title LIKE 'ZZTEST-%'")
        await conn.execute("DELETE FROM rag_feedback WHERE query_text LIKE 'zztest%'")
        await conn.execute("DELETE FROM rag_refusal_log WHERE query_text LIKE 'zztest%'")
    finally:
        await conn.close()


async def test_query_surfaces_the_relevant_regulatory_chunk(seeded_index):
    result = await query_knowledge_base(
        seeded_index, "zztest what is the inspection interval for fire suppression systems",
        role="safety_officer", dsn=POSTGRES_DSN, knowledge_graph_url=KNOWLEDGE_GRAPH_URL, token_minter=TOKEN_MINTER,
    )
    assert result["refused"] is False
    citations = [c["citation"] for c in result["chunks"]]
    assert any("ZZTEST-OISD Clause 4.3" in c for c in citations)


async def test_superseded_document_excluded_from_present_tense_query(seeded_index):
    result = await query_knowledge_base(
        seeded_index, "zztest outdated isolation procedure",
        role="safety_officer", dsn=POSTGRES_DSN, knowledge_graph_url=KNOWLEDGE_GRAPH_URL, token_minter=TOKEN_MINTER,
    )
    chunk_ids = {c["chunk_id"] for c in result["chunks"]}
    all_chunk_ids = {c.metadata.chunk_id for c in seeded_index.chunks if "ZZTEST-Old SOP" in c.metadata.citation_template}
    assert chunk_ids.isdisjoint(all_chunk_ids)


async def test_superseded_document_included_for_historical_as_of_query(seeded_index):
    as_of = datetime.now(timezone.utc) - timedelta(days=30)
    result = await query_knowledge_base(
        seeded_index, "zztest outdated isolation procedure",
        role="safety_officer", dsn=POSTGRES_DSN, knowledge_graph_url=KNOWLEDGE_GRAPH_URL, token_minter=TOKEN_MINTER, as_of=as_of,
    )
    citations = [c["citation"] for c in result["chunks"]]
    assert any("ZZTEST-Old SOP" in c for c in citations)


async def test_restricted_document_hidden_from_viewer_role(seeded_index):
    result = await query_knowledge_base(
        seeded_index, "zztest valve seal inspection compliance audit finding",
        role="viewer", dsn=POSTGRES_DSN, knowledge_graph_url=KNOWLEDGE_GRAPH_URL, token_minter=TOKEN_MINTER,
    )
    citations = [c["citation"] for c in result["chunks"]]
    assert not any("ZZTEST-Audit" in c for c in citations)


async def test_restricted_document_visible_to_safety_officer_role(seeded_index):
    result = await query_knowledge_base(
        seeded_index, "zztest valve seal inspection compliance audit finding",
        role="safety_officer", dsn=POSTGRES_DSN, knowledge_graph_url=KNOWLEDGE_GRAPH_URL, token_minter=TOKEN_MINTER,
    )
    citations = [c["citation"] for c in result["chunks"]]
    assert any("ZZTEST-Audit" in c for c in citations)


async def test_nonsense_query_is_refused(seeded_index):
    result = await query_knowledge_base(
        seeded_index, "zztest xk7 qplj wobbledeglorp banana spaceship 9942",
        role="safety_officer", dsn=POSTGRES_DSN, knowledge_graph_url=KNOWLEDGE_GRAPH_URL, token_minter=TOKEN_MINTER,
    )
    assert result["refused"] is True


async def test_feedback_recording_round_trip():
    await ensure_feedback_tables(POSTGRES_DSN)
    await record_feedback(POSTGRES_DSN, query_text="zztest sample query", chunk_id="c_1_0", signal="negative")

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        row = await conn.fetchrow("SELECT * FROM rag_feedback WHERE query_text = 'zztest sample query'")
    finally:
        await conn.close()
    assert row is not None
    assert row["signal"] == "negative"
