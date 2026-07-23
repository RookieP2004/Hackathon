"""
Emergency Agent — AGENT_ARCHITECTURE.md §9. Given a Critical-severity
Prediction Agent assertion, checks Permit Agent (a real, synchronous bus
request/response call) and, once clean, runs the full Emergency Response
Orchestrator flow (app/orchestrator/flow.py): Generate Incident, Notify
Users, Notify Emergency Team, Activate Evacuation, Generate Timeline,
Capture Sensor Data, Store Evidence, Generate AI Summary, Generate Report,
Create Regulatory Report -- all automatically, every step logged onto the
real incident's append-only timeline as it happens.

Fails closed, the most strictly of any agent in the fleet (§9): this
agent's own unavailability must never look like "no automated response was
needed" -- it looks like a loud escalation instead. The permit gate remains
absolute: no automation below runs at all if the permit check fails or is
unreachable.
"""

from __future__ import annotations

import asyncpg
import httpx
import structlog

from aegis_agents import BaseAgent
from aegis_agents.db import acquire
from app.agents import topics
from app.orchestrator.clients import ServiceClients
from app.orchestrator.flow import run_automatic_emergency_response

logger = structlog.get_logger(__name__)


class EmergencyAgent(BaseAgent):
    agent_id = "emergency-agent"
    failure_mode = "fail_closed"
    tick_interval_seconds = 20.0

    def __init__(
        self, bus, postgres_dsn: str, *, predictive_risk_engine_url: str, incident_service_url: str,
        notification_service_url: str, rag_service_url: str, jwt_secret: str, jwt_algorithm: str,
        pg_pool: asyncpg.Pool | None = None,
    ) -> None:
        super().__init__(bus, postgres_dsn, pg_pool)
        self._predictive_risk_engine_url = predictive_risk_engine_url
        self._clients = ServiceClients(
            postgres_dsn=postgres_dsn, incident_service_url=incident_service_url,
            notification_service_url=notification_service_url, rag_service_url=rag_service_url,
            jwt_secret=jwt_secret, jwt_algorithm=jwt_algorithm,
        )

    async def tick(self) -> None:
        return  # this agent's Core is subscription-driven; see run_subscriber_loop

    async def run_subscriber_loop(self) -> None:
        async for message in self.bus.subscribe(topics.ASSERTION):
            if message.payload.get("severity") == "critical" and message.payload.get("hazard_class"):
                try:
                    await self._handle_critical_risk(message)
                except Exception as exc:  # noqa: BLE001 -- one bad assertion must never kill this loop for every future one (§9's fail-closed guarantee only holds if the loop keeps running)
                    logger.warning("emergency_agent_handler_failed", error=str(exc), correlation_id=message.correlation_id)
                    try:
                        await self.escalate(
                            reason=f"Emergency Agent's own handling of a critical assertion raised an unexpected error ({exc}) -- failing closed, escalating for manual response.",
                            confidence=1.0, evidence_refs=[], payload={"error": str(exc)}, correlation_id=message.correlation_id,
                        )
                    except Exception:
                        logger.error("emergency_agent_escalation_also_failed", correlation_id=message.correlation_id)

    async def _handle_critical_risk(self, message) -> None:
        equipment_id = message.payload.get("equipment_id")
        zone_id = message.payload.get("zone_id")
        hazard_class = message.payload.get("hazard_class")

        # A sustained critical condition re-fires this handler on every
        # Prediction Agent tick (as often as every ~10-30s) -- without this
        # check, each tick would run the entire response flow again: a new
        # incident, two more alerts, a fresh evacuation event, and two more
        # PDFs, indefinitely, for what a real DCS would treat as one ongoing
        # condition. An already-open incident on this equipment means the
        # automated response already ran; let a human close it before this
        # agent runs it again.
        if equipment_id is not None and await self._has_open_incident(equipment_id):
            await self.memory.log_decision(
                decision="response_suppressed_existing_incident",
                reasoning=f"Equipment {equipment_id} already has an open incident -- suppressing a duplicate automatic response to this critical {hazard_class} assertion.",
                confidence=1.0, evidence_refs=[f"equipment:{equipment_id}"], correlation_id=message.correlation_id,
            )
            return

        permit_response = await self.request(
            target_topic=topics.PERMIT_CONFLICT_CHECK_REQUEST, response_topic=f"{self.agent_id}.response",
            payload={"equipment_id": equipment_id, "action_description": f"emergency response to {hazard_class}"},
            timeout=5.0,
        )
        if permit_response is None:
            # Fail-closed (§9/§4): Permit Agent unreachable -- treat as a potential conflict, escalate, do not proceed.
            await self.escalate(
                reason=f"Permit Agent unreachable while responding to critical {hazard_class} risk on equipment {equipment_id} -- failing closed.",
                confidence=1.0, evidence_refs=[f"equipment:{equipment_id}"], payload={"equipment_id": equipment_id, "hazard_class": hazard_class},
                correlation_id=message.correlation_id,
            )
            return

        if permit_response.payload.get("verdict") == "flag_for_human_review":
            await self.escalate(
                reason=f"Permit conflict blocks automated response to {hazard_class} on equipment {equipment_id}: {permit_response.payload.get('reason')}",
                confidence=1.0, evidence_refs=[f"equipment:{equipment_id}"], payload={"equipment_id": equipment_id, "hazard_class": hazard_class},
                correlation_id=message.correlation_id,
            )
            return

        assessment = await self._fetch_current_assessment(equipment_id, hazard_class)
        if assessment is None:
            await self.escalate(
                reason=f"Could not fetch a fresh Risk Fusion Engine assessment for equipment {equipment_id}/{hazard_class} -- failing closed, no automated response executed.",
                confidence=1.0, evidence_refs=[f"equipment:{equipment_id}"], payload={"equipment_id": equipment_id, "hazard_class": hazard_class},
                correlation_id=message.correlation_id,
            )
            return

        try:
            result = await run_automatic_emergency_response(
                self._clients, self.postgres_dsn, hazard_class=hazard_class, equipment_id=equipment_id,
                equipment_tag=assessment["equipment_tag"], zone_id=zone_id or assessment.get("zone_id"),
                plant_id=await self._resolve_plant_id(zone_id or assessment.get("zone_id")),
                score=assessment["score"], severity=assessment["severity"], confidence=assessment["posterior_probability"],
                contributing_factors=assessment["contributing_factors"], recommendations=assessment["recommendations"],
                counterfactuals=assessment["counterfactuals"], pg_pool=self.pg_pool,
            )
        except httpx.HTTPError as exc:
            await self.escalate(
                reason=f"Automated emergency response for {hazard_class} on equipment {equipment_id} failed mid-flow ({exc}) -- failing closed, escalating for manual completion.",
                confidence=1.0, evidence_refs=[f"equipment:{equipment_id}"], payload={"equipment_id": equipment_id, "hazard_class": hazard_class},
                correlation_id=message.correlation_id,
            )
            return

        reasoning = (
            f"Critical {hazard_class} risk on equipment {equipment_id} (zone {zone_id}): permit check clean "
            f"({permit_response.payload.get('reason')}). Ran the full automatic Emergency Response Orchestrator flow "
            f"({len(result.timeline)} steps: {', '.join(result.timeline)}) against incident {result.incident_number}."
        )
        await self.memory.log_decision(
            decision="automatic_emergency_response_completed", reasoning=reasoning, confidence=message.confidence or 0.9,
            evidence_refs=[f"equipment:{equipment_id}", f"incident:{result.incident_id}"], correlation_id=message.correlation_id,
        )
        await self.escalate(
            reason=f"Automated emergency response completed for incident {result.incident_number} (critical {hazard_class}) -- {len(result.timeline)} steps executed automatically.",
            confidence=message.confidence or 0.9, evidence_refs=[f"incident:{result.incident_id}"],
            payload={
                "incident_id": result.incident_id, "incident_number": result.incident_number, "equipment_id": equipment_id,
                "hazard_class": hazard_class, "timeline": result.timeline, "incident_report_path": result.incident_report_path,
                "regulatory_report_path": result.regulatory_report_path,
            },
            correlation_id=message.correlation_id,
        )

    async def _has_open_incident(self, equipment_id: int) -> bool:
        async with acquire(self.postgres_dsn, self.pg_pool) as conn:
            row = await conn.fetchrow("SELECT id FROM incidents WHERE equipment_id = $1 AND status != 'closed' LIMIT 1", equipment_id)
        return row is not None

    async def _fetch_current_assessment(self, equipment_id: int | None, hazard_class: str) -> dict | None:
        if equipment_id is None:
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(f"{self._predictive_risk_engine_url}/fusion/assess/{equipment_id}", headers=await self._clients.auth_headers())
                response.raise_for_status()
                assessments = response.json()["assessments"]
        except httpx.HTTPError as exc:
            logger.warning("assessment_fetch_failed", equipment_id=equipment_id, error=str(exc))
            return None
        return next((a for a in assessments if a["hazard_class"] == hazard_class), None)

    async def _resolve_plant_id(self, zone_id: int | None) -> int:
        if zone_id is None:
            return 1
        async with acquire(self.postgres_dsn, self.pg_pool) as conn:
            row = await conn.fetchrow("SELECT b.plant_id FROM zones z JOIN buildings b ON b.id = z.building_id WHERE z.id = $1", zone_id)
        return row["plant_id"] if row else 1
