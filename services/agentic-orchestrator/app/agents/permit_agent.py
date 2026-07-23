"""
Permit Agent — AGENT_ARCHITECTURE.md §4. A gatekeeper, not a detector: one
of only two agents in the fleet primarily invoked as a blocking
request/response query rather than an async publisher (§4's own framing).
Wraps the real knowledge-graph service's `/graph/equipment/{id}/permit-
conflict` endpoint (built in the Neo4j pass) -- the Core here is a
deterministic database/graph lookup, never a probabilistic claim.

Fails closed (§4): if the conflict check cannot be completed, the verdict is
"flag for human review", never "assume no conflict."
"""

from __future__ import annotations

import httpx
import structlog

from aegis_agents import BaseAgent
from aegis_api_common import ServiceActorTokenMinter
from app.agents import topics

logger = structlog.get_logger(__name__)


class PermitAgent(BaseAgent):
    agent_id = "permit-agent"
    failure_mode = "fail_closed"
    tick_interval_seconds = 30.0  # heartbeat/bookkeeping cadence only -- the real work is the subscriber loop

    def __init__(self, bus, postgres_dsn: str, knowledge_graph_url: str, *, jwt_secret: str, jwt_algorithm: str) -> None:
        super().__init__(bus, postgres_dsn)
        self._knowledge_graph_url = knowledge_graph_url
        self._token_minter = ServiceActorTokenMinter(postgres_dsn=postgres_dsn, jwt_secret=jwt_secret, jwt_algorithm=jwt_algorithm)

    async def tick(self) -> None:
        return  # this agent's Core is entirely request/response-driven; see run_subscriber_loop

    async def run_subscriber_loop(self) -> None:
        async for message in self.bus.subscribe(topics.PERMIT_CONFLICT_CHECK_REQUEST):
            try:
                await self._handle_conflict_check(message)
            except Exception as exc:  # noqa: BLE001 -- one bad request must never kill this loop for every future one
                logger.warning("permit_agent_handler_failed", error=str(exc), correlation_id=message.correlation_id)
                try:
                    await self.respond(to=message, payload={"verdict": "flag_for_human_review", "reason": f"Unexpected error: {exc}"}, confidence=1.0)
                except Exception:
                    logger.error("permit_agent_response_also_failed", correlation_id=message.correlation_id)

    async def _handle_conflict_check(self, message) -> None:
        equipment_id = message.payload.get("equipment_id")
        action_description = message.payload.get("action_description", "an unspecified action")

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(
                    f"{self._knowledge_graph_url}/graph/equipment/{equipment_id}/permit-conflict",
                    headers=await self._token_minter.auth_headers(),
                )
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPError as exc:
            # Fail-closed (§4): unreachable means "cannot verify", never "no conflict."
            reasoning = f"Permit conflict check for equipment {equipment_id} could not be completed ({exc}) -- failing closed, treating as a potential conflict."
            await self.memory.log_decision(decision="conflict_check_failed_closed", reasoning=reasoning, confidence=1.0, evidence_refs=[f"equipment:{equipment_id}"], correlation_id=message.correlation_id)
            await self.respond(to=message, payload={"verdict": "flag_for_human_review", "reason": reasoning}, confidence=1.0)
            return

        has_conflict = result["has_conflict"]
        verdict = "flag_for_human_review" if has_conflict else "approve"
        permit_numbers = [p["permitNumber"] for p in result["active_permits"]]
        reasoning = (
            f"{len(permit_numbers)} active permit(s) found in scope for equipment {equipment_id} ({', '.join(permit_numbers) or 'none'}) "
            f"evaluating proposed action '{action_description}'."
        )

        await self.memory.log_decision(
            decision=verdict, reasoning=reasoning, confidence=1.0,  # a database fact, never scored as uncertain (§4)
            evidence_refs=[f"equipment:{equipment_id}"] + [f"permit:{p}" for p in permit_numbers],
            correlation_id=message.correlation_id,
        )
        await self.respond(to=message, payload={"verdict": verdict, "active_permits": permit_numbers, "reason": reasoning}, confidence=1.0)

        if has_conflict:
            await self.escalate(
                reason=f"Permit conflict detected for equipment {equipment_id}: {reasoning}",
                confidence=1.0, evidence_refs=[f"equipment:{equipment_id}"], payload={"equipment_id": equipment_id, "active_permits": permit_numbers},
                correlation_id=message.correlation_id,
            )
