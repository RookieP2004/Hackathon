"""
Knowledge Agent — AGENT_ARCHITECTURE.md §6. The fronting service for the RAG
vector store and the sole authorized writer to the Knowledge Graph -- both
already real, running services (rag-service, knowledge-graph) built in
earlier passes. This agent is the fleet-facing shell: a synchronous
request/response wrapper around rag-service's real `/rag/query` endpoint,
under the same strict grounding discipline (never answer without a citation
above a minimum relevance threshold) that endpoint already enforces.
"""

from __future__ import annotations

import time

import asyncpg
import httpx
import structlog
from jose import jwt

from aegis_agents import BaseAgent
from app.agents import topics

logger = structlog.get_logger(__name__)

_ROLE_NAME = "safety_officer"


class KnowledgeAgent(BaseAgent):
    agent_id = "knowledge-agent"
    failure_mode = "fail_open"  # "reduced-grounding" labeling per §6, never a hard block
    tick_interval_seconds = 30.0

    def __init__(self, bus, postgres_dsn: str, rag_service_url: str, jwt_secret: str, jwt_algorithm: str) -> None:
        super().__init__(bus, postgres_dsn)
        self._rag_service_url = rag_service_url
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0

    async def tick(self) -> None:
        return

    async def run_subscriber_loop(self) -> None:
        async for message in self.bus.subscribe(topics.KNOWLEDGE_QUERY_REQUEST):
            try:
                await self._handle_query(message)
            except Exception as exc:  # noqa: BLE001 -- one bad query must never kill this loop for every future one
                logger.warning("knowledge_agent_handler_failed", error=str(exc), correlation_id=message.correlation_id)
                try:
                    await self.respond(to=message, payload={"refused": True, "reason": f"Unexpected error: {exc}", "chunks": []}, confidence=0.0)
                except Exception:
                    logger.error("knowledge_agent_response_also_failed", correlation_id=message.correlation_id)

    async def _get_token(self) -> str:
        now = time.time()
        if self._cached_token and now < self._token_expires_at - 30:
            return self._cached_token
        conn = await asyncpg.connect(self.postgres_dsn)
        try:
            row = await conn.fetchrow(
                "SELECT u.id, u.default_role_id FROM users u JOIN roles r ON r.id = u.default_role_id WHERE r.name = $1 LIMIT 1",
                _ROLE_NAME,
            )
        finally:
            await conn.close()
        expires_at = now + 600
        token = jwt.encode(
            {"sub": str(row["id"]), "role_id": row["default_role_id"], "type": "access", "exp": int(expires_at)},
            self._jwt_secret, algorithm=self._jwt_algorithm,
        )
        self._cached_token, self._token_expires_at = token, expires_at
        return token

    async def _handle_query(self, message) -> None:
        query_text = message.payload.get("query", "")
        try:
            token = await self._get_token()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self._rag_service_url}/rag/query", json={"query": query_text},
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPError as exc:
            reasoning = f"Query could not be grounded: rag-service unreachable ({exc}) -- reduced-grounding fallback, no context sources available."
            await self.memory.log_decision(decision="query_failed_reduced_grounding", reasoning=reasoning, confidence=0.0, evidence_refs=[], correlation_id=message.correlation_id)
            await self.respond(to=message, payload={"refused": True, "reason": reasoning, "chunks": []}, confidence=0.0)
            return

        if result["refused"]:
            reasoning = f"Query '{query_text}' could not be answered above the minimum confidence threshold -- explicit refusal rather than an ungrounded guess."
        else:
            citations = [c["citation"] for c in result["chunks"][:3]]
            reasoning = f"Query '{query_text}' answered with {len(result['chunks'])} grounded chunk(s), top citations: {citations}."

        await self.memory.log_decision(
            decision="query_answered" if not result["refused"] else "query_refused",
            reasoning=reasoning, confidence=result.get("top_confidence") or 0.0,
            evidence_refs=[c["chunk_id"] for c in result["chunks"]], correlation_id=message.correlation_id,
        )
        await self.respond(to=message, payload=result, confidence=result.get("top_confidence"))
