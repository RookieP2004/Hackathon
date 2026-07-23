"""
Stage 2 — Graph-Constrained Candidate Generation (RISK_FUSION_ENGINE.md
§3.2). "Which of the available Evidence Nodes are even structurally eligible
to be evidence for which hazard hypothesis?" -- answered by a real call to
the knowledge-graph service's `/graph/equipment/{id}/risk-context` endpoint
(built in the previous pass), not a re-implementation of graph traversal
here. A sensor with no graph-admitted path to the equipment under assessment
is excluded entirely, never merely down-weighted (§3.2's own wording).
"""

from __future__ import annotations

import httpx
import structlog

from aegis_api_common import ServiceActorTokenMinter

logger = structlog.get_logger(__name__)


class GraphCandidateError(Exception):
    pass


async def fetch_risk_context(knowledge_graph_url: str, equipment_id: int, token_minter: ServiceActorTokenMinter) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{knowledge_graph_url}/graph/equipment/{equipment_id}/risk-context", headers=await token_minter.auth_headers(),
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise GraphCandidateError(f"Equipment {equipment_id} has no graph node -- has /graph/sync been run?") from exc
            raise
        except httpx.HTTPError as exc:
            logger.warning("graph_risk_context_failed", equipment_id=equipment_id, error=str(exc))
            raise GraphCandidateError(str(exc)) from exc


async def fetch_permit_conflict(knowledge_graph_url: str, equipment_id: int, token_minter: ServiceActorTokenMinter) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{knowledge_graph_url}/graph/equipment/{equipment_id}/permit-conflict", headers=await token_minter.auth_headers(),
        )
        response.raise_for_status()
        return response.json()


async def fetch_similar_incidents(knowledge_graph_url: str, equipment_id: int, token_minter: ServiceActorTokenMinter, limit: int = 5) -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{knowledge_graph_url}/graph/equipment/{equipment_id}/similar-incidents",
            params={"limit": limit}, headers=await token_minter.auth_headers(),
        )
        response.raise_for_status()
        return response.json()["incidents"]


async def post_risk_to_graph(knowledge_graph_url: str, risk_payload: dict, token_minter: ServiceActorTokenMinter) -> dict | None:
    """§5.3 of KNOWLEDGE_GRAPH.md -- anchors this assessment's Evidence Bundle
    into the graph via the `/graph/risk` endpoint built specifically for this."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(f"{knowledge_graph_url}/graph/risk", json=risk_payload, headers=await token_minter.auth_headers())
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.warning("graph_risk_anchor_failed", error=str(exc))
            return None
