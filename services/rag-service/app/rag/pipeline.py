"""
Orchestrates hybrid search (retrieval.py) -> re-ranking (reranking.py) ->
low-confidence refusal + conflict detection (hallucination.py) into one
grounded, cited result set. Deliberately stops short of free-text
generation (RAG_SYSTEM.md §8.2) -- this is the API surface the (not-yet-
built) AI Copilot calls and layers conversational generation over; see
retrieval.py/hallucination.py's docstrings for why generation itself needs
an LLM this environment has no API key configured for, while everything
here does not.
"""

from __future__ import annotations

from datetime import datetime, timezone

from aegis_api_common import ServiceActorTokenMinter

from app.rag.hallucination import detect_numeric_conflicts, should_refuse
from app.rag.reranking import rerank
from app.rag.retrieval import hybrid_search
from app.rag.store import ChunkIndex, record_refusal


async def query_knowledge_base(
    index: ChunkIndex, query_text: str, *, role: str, dsn: str, knowledge_graph_url: str, token_minter: ServiceActorTokenMinter,
    as_of: datetime | None = None, equipment_id: int | None = None, zone_id: int | None = None,
    top_k: int = 20, top_n: int = 10,
) -> dict:
    as_of = as_of or datetime.now(timezone.utc)

    candidates = await hybrid_search(
        index, query_text, role=role, as_of=as_of, top_k=top_k, token_minter=token_minter,
        equipment_id=equipment_id, zone_id=zone_id, knowledge_graph_url=knowledge_graph_url,
    )
    reranked = rerank(query_text, candidates, top_n=top_n)

    top_score = reranked[0]["score"] if reranked else None
    top_raw_score = reranked[0]["raw_score"] if reranked else None
    refuse, reason = should_refuse(top_score, top_raw_score)
    if refuse:
        await record_refusal(dsn, query_text=query_text, reason=reason or "unknown")
        return {"refused": True, "reason": reason, "chunks": [], "conflicts": [], "top_confidence": top_score}

    conflicts = detect_numeric_conflicts(reranked)
    return {
        "refused": False,
        "reason": None,
        "top_confidence": top_score,
        "chunks": [
            {
                "chunk_id": r["chunk"].metadata.chunk_id,
                "text": r["chunk"].text,
                "citation": r["chunk"].metadata.citation_template,
                "score": r["score"],
                "graph_linked": r["graph_linked"],
                "metadata": r["chunk"].metadata.to_dict(),
            }
            for r in reranked
        ],
        "conflicts": conflicts,
    }
