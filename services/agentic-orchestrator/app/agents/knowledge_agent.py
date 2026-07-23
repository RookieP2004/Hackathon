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

import asyncpg
import httpx
import structlog

from aegis_agents import BaseAgent
from aegis_api_common import ServiceActorTokenMinter
from app.agents import topics

logger = structlog.get_logger(__name__)


class KnowledgeAgent(BaseAgent):
    agent_id = "knowledge-agent"
    failure_mode = "fail_open"  # "reduced-grounding" labeling per §6, never a hard block
    tick_interval_seconds = 30.0

    def __init__(
        self, bus, postgres_dsn: str, rag_service_url: str, jwt_secret: str, jwt_algorithm: str,
        pg_pool: asyncpg.Pool | None = None,
    ) -> None:
        super().__init__(bus, postgres_dsn, pg_pool)
        self._rag_service_url = rag_service_url
        self._token_minter = ServiceActorTokenMinter(postgres_dsn=postgres_dsn, jwt_secret=jwt_secret, jwt_algorithm=jwt_algorithm)

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

    async def _handle_query(self, message) -> None:
        query_text = message.payload.get("query", "")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self._rag_service_url}/rag/query", json={"query": query_text},
                    headers=await self._token_minter.auth_headers(),
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
