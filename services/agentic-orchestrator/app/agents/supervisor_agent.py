"""
Supervisor Agent — AGENT_ARCHITECTURE.md §12. The hub of the entire Agent
Bus: the only agent with a standing subscription to every inter-agent topic,
maintaining the fleet's collective health state and arbitrating disagreement
via a documented conservative-precedence rule (never downgrade a Critical
assertion via averaging or consensus).

This environment has no LLM API key configured anywhere (confirmed while
building the RAG pipeline) -- §12's "LLM-assisted synthesis... only to
compose the human-facing explanation of a disagreement" therefore always
takes the hard-coded fallback path §12's own Failure Handling section
describes for this agent's *unavailability* ("escalate every unresolved
disagreement directly to a human, no LLM arbitration available"). That
fallback is not a degraded special case here -- it is simply how this
agent runs, and it happens to be a fully deterministic, real rule, not a
placeholder: never downgrade a Critical assertion, always surface
disagreement explicitly rather than resolve it unilaterally.
"""

from __future__ import annotations

import asyncio
import time

import asyncpg
import structlog

from aegis_agents import BaseAgent
from app.agents import topics

logger = structlog.get_logger(__name__)

DISAGREEMENT_WINDOW_SECONDS = 120
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class SupervisorAgent(BaseAgent):
    agent_id = "supervisor-agent"
    failure_mode = "fail_closed"
    tick_interval_seconds = 15.0

    def __init__(self, bus, postgres_dsn: str, pg_pool: asyncpg.Pool | None = None) -> None:
        super().__init__(bus, postgres_dsn, pg_pool)
        self.fleet_health: dict[str, dict] = {}
        self._recent_assertions: dict[str, list[tuple[str, dict, float]]] = {}

    async def tick(self) -> None:
        self._age_out_stale_assertions()

    async def run_subscriber_loop(self) -> None:
        async for message in self.bus.subscribe(topics.ASSERTION, topics.ESCALATION, topics.HEALTH):
            try:
                if message.message_type.value == "health":
                    self.fleet_health[message.agent_id] = message.payload
                elif message.message_type.value == "assertion":
                    await self._track_and_arbitrate(message)
                elif message.message_type.value == "escalation":
                    await self.memory.log_decision(
                        decision="escalation_observed", reasoning=f"Escalation from {message.agent_id}: {message.payload.get('reason', message.reasoning or '')}",
                        confidence=message.confidence, evidence_refs=message.evidence_refs, correlation_id=message.correlation_id,
                    )
            except Exception as exc:  # noqa: BLE001 -- Supervisor is the fleet's only standing subscriber across every topic; one bad message must never deafen it for every message after
                logger.warning("supervisor_agent_handler_failed", error=str(exc), correlation_id=message.correlation_id)

    def _age_out_stale_assertions(self) -> None:
        now = time.time()
        for key in list(self._recent_assertions):
            self._recent_assertions[key] = [
                (agent_id, payload, ts) for agent_id, payload, ts in self._recent_assertions[key]
                if now - ts < DISAGREEMENT_WINDOW_SECONDS
            ]
            if not self._recent_assertions[key]:
                del self._recent_assertions[key]

    async def _track_and_arbitrate(self, message) -> None:
        severity = message.payload.get("severity")
        equipment_id = message.payload.get("equipment_id")
        if severity is None or equipment_id is None:
            return  # only severity-bearing, equipment-scoped assertions participate in arbitration

        key = f"equipment:{equipment_id}"
        bucket = self._recent_assertions.setdefault(key, [])
        bucket.append((message.agent_id, {"severity": severity, "confidence": message.confidence}, time.time()))

        distinct_agents = {agent_id for agent_id, _, _ in bucket}
        if len(distinct_agents) < 2:
            return

        severities = {agent_id: payload["severity"] for agent_id, payload, _ in bucket}
        distinct_severities = set(severities.values())
        if len(distinct_severities) < 2:
            return  # agreement -- nothing to arbitrate

        highest_agent = max(severities, key=lambda a: SEVERITY_RANK.get(severities[a], 0))
        highest_severity = severities[highest_agent]

        reasoning = (
            f"Agents disagree on severity for equipment {equipment_id}: {severities}. Conservative-precedence rule "
            f"applied -- '{highest_severity}' (from {highest_agent}) is never downgraded by another agent's lower "
            f"assessment or by averaging; both claims are surfaced explicitly for human resolution rather than "
            f"this agent choosing between them (no LLM arbitration is configured in this environment, so this is "
            f"always the hard-coded fallback path §12 specifies for Supervisor Agent unavailability -- here, simply the normal path)."
        )
        await self.escalate(
            reason=reasoning, confidence=1.0, evidence_refs=[key],
            payload={"equipment_id": equipment_id, "disagreement": severities, "precedence_severity": highest_severity},
            correlation_id=message.correlation_id,
        )
        self._recent_assertions[key] = []  # this disagreement has been surfaced -- don't re-fire on the same bucket every tick
