"""
The chunk index — a rebuildable, in-memory materialized view over
`knowledge_documents` (the real system of record, already in Postgres),
following the same "derived, rebuildable projection" pattern the Neo4j graph
uses (KNOWLEDGE_GRAPH.md §7): chunking + embedding is cheap enough to redo at
service startup / on `POST /rag/reindex` that persisting a separate vector
database is unneeded operational surface for this corpus's size. Both
currently-effective AND superseded documents are indexed -- the temporal
filter (§5.4) is a query-time concern, not an index-time one, since a
historical query must still be able to retrieve a superseded version.

Feedback (§10) is the one thing genuinely worth persisting past a restart --
real user signal, not a derived index -- so it lives in a small
self-managed Postgres table (created directly by this service, not through
the shared libs/db Alembic chain, matching computer-vision's precedent of
services that don't need the full ORM/migration machinery for one narrow
table).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import asyncpg
from rank_bm25 import BM25Okapi

from app.rag.schema import Chunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def cosine_similarity(a: list[float], b: list[float]) -> float:
    # Embeddings are stored L2-normalized (embeddings.py's normalize_embeddings=True),
    # so the dot product already equals cosine similarity -- no separate norm step needed.
    return sum(x * y for x, y in zip(a, b))


class ChunkIndex:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self._bm25: BM25Okapi | None = None

    def rebuild(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        tokenized_corpus = [tokenize(c.text) for c in chunks]
        self._bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None

    def bm25_scores(self, query: str) -> list[float]:
        if self._bm25 is None:
            return [0.0] * len(self.chunks)
        return list(self._bm25.get_scores(tokenize(query)))

    def vector_scores(self, query_embedding: list[float]) -> list[float]:
        return [cosine_similarity(query_embedding, c.embedding) for c in self.chunks]

    @property
    def size(self) -> int:
        return len(self.chunks)


chunk_index = ChunkIndex()


@dataclass
class FeedbackRecord:
    id: int
    query_text: str
    chunk_id: str
    signal: str  # 'positive' | 'negative'
    created_at: str


FEEDBACK_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS rag_feedback (
    id BIGSERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    signal TEXT NOT NULL CHECK (signal IN ('positive', 'negative')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

REFUSAL_LOG_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS rag_refusal_log (
    id BIGSERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


async def ensure_feedback_tables(dsn: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(FEEDBACK_TABLE_DDL)
        await conn.execute(REFUSAL_LOG_TABLE_DDL)
    finally:
        await conn.close()


async def record_feedback(dsn: str, *, query_text: str, chunk_id: str, signal: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            "INSERT INTO rag_feedback (query_text, chunk_id, signal) VALUES ($1, $2, $3)",
            query_text, chunk_id, signal,
        )
    finally:
        await conn.close()


async def record_refusal(dsn: str, *, query_text: str, reason: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            "INSERT INTO rag_refusal_log (query_text, reason) VALUES ($1, $2)", query_text, reason,
        )
    finally:
        await conn.close()


async def corpus_gap_report(dsn: str, *, min_occurrences: int = 2) -> dict:
    """§10.1's corpus-gap detection: a query repeatedly receiving negative
    feedback, or repeatedly triggering the low-confidence refusal (§9 layer
    4), is escalated as a documentation-gap item for the Safety Officer role."""
    conn = await asyncpg.connect(dsn)
    try:
        negative_feedback = await conn.fetch(
            """
            SELECT query_text, count(*) AS occurrences
            FROM rag_feedback WHERE signal = 'negative'
            GROUP BY query_text HAVING count(*) >= $1
            ORDER BY occurrences DESC
            """,
            min_occurrences,
        )
        repeated_refusals = await conn.fetch(
            """
            SELECT query_text, count(*) AS occurrences
            FROM rag_refusal_log
            GROUP BY query_text HAVING count(*) >= $1
            ORDER BY occurrences DESC
            """,
            min_occurrences,
        )
    finally:
        await conn.close()
    return {
        "repeated_negative_feedback": [dict(r) for r in negative_feedback],
        "repeated_refusals": [dict(r) for r in repeated_refusals],
    }
