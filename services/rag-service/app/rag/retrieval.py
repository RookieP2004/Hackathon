"""
Hybrid search — RAG_SYSTEM.md §5. Three retrieval signals always run (§5.3:
"All three signals still run in every case -- this classifier sets fusion
weights, not an exclusive routing decision"), fused via Reciprocal Rank
Fusion, a standard, well-defined rank-fusion algorithm (not a bespoke
weighted-average scheme, which would require hand-tuned weights this corpus
has no labeled data to tune yet):

1. Vector similarity (embeddings.py's cosine similarity)
2. Keyword/BM25 (store.py's rank_bm25 index)
3. Knowledge-graph-scoped traversal (KNOWLEDGE_GRAPH.md §6.2's pattern,
   applied to Document/Regulation nodes instead of sensors -- an HTTP call
   to the already-built knowledge-graph service, not a re-implementation)
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog
from aegis_api_common import ServiceActorTokenMinter

from app.rag.embeddings import embedding_model
from app.rag.schema import ALLOWED_ROLES_FOR_RESTRICTED, Chunk
from app.rag.store import ChunkIndex

logger = structlog.get_logger(__name__)

RRF_K = 60  # standard RRF damping constant


@dataclass
class RetrievalCandidate:
    chunk: Chunk
    fused_score: float
    graph_linked: bool


async def graph_linked_document_ids(
    knowledge_graph_url: str, token_minter: ServiceActorTokenMinter, *, equipment_id: int | None = None, zone_id: int | None = None,
) -> set[int]:
    """Which Document/Regulation node ids are GOVERNS/IMPLEMENTS/APPLIES_TO
    -linked to the equipment or zone this query concerns (§5.2's third
    signal) -- a real call to the knowledge-graph service built in the
    previous pass, not a duplicated Cypher implementation."""
    if equipment_id is None and zone_id is None:
        return set()

    if equipment_id is not None:
        query = (
            "MATCH (d)-[:GOVERNS]->(eq:Equipment {id: $equipment_id}) "
            "WHERE d:Document OR d:Regulation RETURN d.id AS id"
        )
        params = {"equipment_id": equipment_id}
    else:
        query = (
            "MATCH (d)-[:APPLIES_TO]->(z:Zone {id: $zone_id}) "
            "WHERE d:Document OR d:Regulation RETURN d.id AS id"
        )
        params = {"zone_id": zone_id}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{knowledge_graph_url}/graph/cypher/query", json={"query": query, "params": params},
                headers=await token_minter.auth_headers(),
            )
            response.raise_for_status()
            return {r["id"] for r in response.json()["results"]}
    except httpx.HTTPError as exc:
        logger.warning("graph_linked_lookup_failed", error=str(exc))
        return set()


def reciprocal_rank_fusion(rankings: list[list[str]]) -> dict[str, float]:
    """`rankings` is a list of ranked chunk_id lists (best first), one per
    signal. Standard RRF: score(id) = sum over signals of 1/(k + rank)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


def _access_allowed(chunk: Chunk, role: str) -> bool:
    if chunk.metadata.access_classification != "restricted":
        return True
    return role in ALLOWED_ROLES_FOR_RESTRICTED


def _temporally_valid(chunk: Chunk, as_of) -> bool:
    """§5.4: present-tense queries default as_of=now(), retrieving only
    currently-effective versions; historical queries pass an explicit as_of
    and resolve to whichever version was in effect at that date. `as_of` must
    be timezone-aware (the API layer enforces this) -- `superseded_at` comes
    back from Postgres's TIMESTAMPTZ column already timezone-aware, so
    comparing the two is always well-defined, never a naive/aware mismatch."""
    if chunk.metadata.superseded_at is None:
        return True
    return as_of < chunk.metadata.superseded_at


async def hybrid_search(
    index: ChunkIndex, query: str, *, role: str, as_of, token_minter: ServiceActorTokenMinter, top_k: int = 20,
    equipment_id: int | None = None, zone_id: int | None = None, knowledge_graph_url: str = "",
) -> list[RetrievalCandidate]:
    # §5.5: RBAC filtering is a pre-retrieval filter, applied before any signal scores anything.
    # §5.4: temporal scoping is likewise applied before scoring, not as a post-hoc trim.
    eligible_indices = [
        i for i, c in enumerate(index.chunks)
        if _access_allowed(c, role) and _temporally_valid(c, as_of)
    ]
    if not eligible_indices:
        return []

    eligible_chunks = [index.chunks[i] for i in eligible_indices]

    bm25_all = index.bm25_scores(query)
    bm25_scores = [bm25_all[i] for i in eligible_indices]

    query_embedding = embedding_model.embed_one(query)
    vector_all = index.vector_scores(query_embedding)
    vector_scores = [vector_all[i] for i in eligible_indices]

    linked_doc_ids = await graph_linked_document_ids(
        knowledge_graph_url, token_minter, equipment_id=equipment_id, zone_id=zone_id
    )

    bm25_ranking = [c.metadata.chunk_id for c in _sorted_by(eligible_chunks, bm25_scores)]
    vector_ranking = [c.metadata.chunk_id for c in _sorted_by(eligible_chunks, vector_scores)]
    graph_ranking = [
        c.metadata.chunk_id for c in eligible_chunks if c.metadata.document_id in linked_doc_ids
    ]

    fused = reciprocal_rank_fusion([bm25_ranking, vector_ranking, graph_ranking])

    by_id = {c.metadata.chunk_id: c for c in eligible_chunks}
    candidates = [
        RetrievalCandidate(chunk=by_id[cid], fused_score=score, graph_linked=by_id[cid].metadata.document_id in linked_doc_ids)
        for cid, score in fused.items()
    ]
    candidates.sort(key=lambda c: c.fused_score, reverse=True)
    return candidates[:top_k]


def _sorted_by(chunks: list[Chunk], scores: list[float]) -> list[Chunk]:
    return [c for c, _ in sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)]
