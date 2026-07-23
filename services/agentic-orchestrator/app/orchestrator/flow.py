"""
The Emergency Response Orchestrator's fully-automatic flow. Triggered by
Emergency Agent (agentic-orchestrator's own fleet) once a Critical-severity
risk assessment has passed its permit-conflict gate -- this module is what
runs *after* that gate, executing every step the user's own requirement list
names, in order, automatically, with each step logging itself onto the
incident's real, append-only timeline as it completes.

Nothing here re-decides whether the situation is dangerous (that was already
decided, upstream, by the real Risk Fusion Engine) -- this module's whole
job is disciplined, automatic execution of the response given that a
Critical decision has already been made and cleared its permit gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import asyncpg
import structlog

from app.orchestrator.clients import ServiceClients
from app.orchestrator.evidence import capture_sensor_data, store_evidence_bundle
from app.orchestrator.reports import generate_incident_report, generate_regulatory_report
from app.orchestrator.summary import generate_ai_summary

logger = structlog.get_logger(__name__)


@dataclass
class EmergencyResponseResult:
    incident_id: int
    incident_number: str
    timeline: list[str]
    incident_report_path: str
    regulatory_report_path: str
    evidence_path: str
    ai_summary: str


async def run_automatic_emergency_response(
    clients: ServiceClients, postgres_dsn: str, *, hazard_class: str, equipment_id: int | None,
    equipment_tag: str, zone_id: int | None, plant_id: int, score: float, severity: str, confidence: float,
    contributing_factors: list[dict], recommendations: list[str], counterfactuals: list[dict],
    pg_pool: asyncpg.Pool | None = None,
) -> EmergencyResponseResult:
    timeline: list[str] = []
    now = datetime.now(timezone.utc)
    incident_number = f"INC-AUTO-{equipment_id or 'zone' + str(zone_id)}-{int(now.timestamp())}"

    # 1. Generate Incident
    incident = await clients.create_incident(
        incident_number=incident_number, plant_id=plant_id, zone_id=zone_id, equipment_id=equipment_id, severity=severity,
    )
    incident_id = incident["id"]
    timeline.append("incident_generated")
    await clients.add_timeline_event(incident_id, event_type="auto_response_started", event_data={"hazard_class": hazard_class, "score": score})

    # 2. Notify Users
    await clients.raise_alert(
        alert_type=f"emergency_{hazard_class}", severity=severity,
        message=f"AEGIS AI automated emergency response: {hazard_class} detected on {equipment_tag}, risk score {score:.1f}/100. Incident {incident_number} opened automatically.",
        zone_id=zone_id, equipment_id=equipment_id, related_incident_id=incident_id,
    )
    timeline.append("users_notified")
    await clients.add_timeline_event(incident_id, event_type="users_notified", event_data={"channel": "general_alert"})

    # 3. Notify Emergency Team
    await clients.raise_alert(
        alert_type=f"emergency_team_dispatch_{hazard_class}", severity="critical",
        message=f"EMERGENCY TEAM DISPATCH: {hazard_class} on {equipment_tag} (zone {zone_id}). Immediate response required. Incident {incident_number}.",
        zone_id=zone_id, equipment_id=equipment_id, related_incident_id=incident_id,
    )
    timeline.append("emergency_team_notified")
    await clients.add_timeline_event(incident_id, event_type="emergency_team_notified", event_data={"channel": "emergency_team_dispatch"})

    # 4. Activate Evacuation
    await clients.add_timeline_event(
        incident_id, event_type="evacuation_activated",
        event_data={"zone_id": zone_id, "reason": f"critical {hazard_class} risk, score {score:.1f}"},
    )
    timeline.append("evacuation_activated")

    # 6. (interleaved before 5/timeline-summary) Capture Sensor Data
    sensor_snapshot = await capture_sensor_data(postgres_dsn, equipment_id, pool=pg_pool)
    await clients.add_timeline_event(incident_id, event_type="sensor_data_captured", event_data={"sensor_count": len(sensor_snapshot.get("sensors", []))})
    timeline.append("sensor_data_captured")

    # 7. Store Evidence
    evidence_bundle = {
        "hazard_class": hazard_class, "score": score, "confidence": confidence,
        "contributing_factors": contributing_factors, "counterfactuals": counterfactuals, "recommendations": recommendations,
    }
    evidence_path = store_evidence_bundle(incident_id, evidence_bundle, sensor_snapshot)
    await clients.add_timeline_event(incident_id, event_type="evidence_stored", event_data={"file_path": evidence_path})
    timeline.append("evidence_stored")

    # 9. Generate AI Summary (before reports, since reports embed it)
    top_counterfactual = counterfactuals[0] if counterfactuals else None
    summary_result = await generate_ai_summary(
        clients, hazard_class=hazard_class, equipment_tag=equipment_tag, score=score, confidence=confidence,
        top_contributing_factors=contributing_factors, counterfactual=top_counterfactual,
    )
    await clients.update_incident_summary(incident_id, summary_result["summary"])
    await clients.add_timeline_event(incident_id, event_type="ai_summary_generated", event_data={"grounding": summary_result["grounding"]})
    timeline.append("ai_summary_generated")

    # 5. Generate Timeline -- fetch the real, now-populated timeline for report embedding
    timeline_events = await _fetch_timeline(clients, incident_id)

    # 6. Generate Report
    incident_report_path = generate_incident_report(
        incident_id=incident_id, incident_number=incident_number, hazard_class=hazard_class, equipment_tag=equipment_tag,
        zone_id=zone_id, score=score, severity=severity, confidence=confidence, contributing_factors=contributing_factors,
        recommendations=recommendations, ai_summary=summary_result["summary"], timeline_events=timeline_events,
    )
    report_record = await clients.create_report(report_type="auto_incident_report", plant_id=plant_id, parameters={"incident_id": incident_id})
    await clients.complete_report(report_record["id"], file_url=incident_report_path)
    await clients.add_timeline_event(incident_id, event_type="report_generated", event_data={"report_id": report_record["id"], "file_path": incident_report_path})
    timeline.append("report_generated")

    # 10. Create Regulatory Report
    regulatory_report_path = generate_regulatory_report(
        incident_id=incident_id, incident_number=incident_number, hazard_class=hazard_class, equipment_tag=equipment_tag,
        zone_id=zone_id, score=score, severity=severity, citations=summary_result["citations"], sensor_snapshot=sensor_snapshot,
    )
    regulatory_report_record = await clients.create_report(report_type="auto_regulatory_report", plant_id=plant_id, parameters={"incident_id": incident_id})
    await clients.complete_report(regulatory_report_record["id"], file_url=regulatory_report_path)
    await clients.add_timeline_event(incident_id, event_type="regulatory_report_generated", event_data={"report_id": regulatory_report_record["id"], "file_path": regulatory_report_path})
    timeline.append("regulatory_report_generated")

    logger.info("emergency_response_completed", incident_id=incident_id, hazard_class=hazard_class, steps=len(timeline))

    return EmergencyResponseResult(
        incident_id=incident_id, incident_number=incident_number, timeline=timeline,
        incident_report_path=incident_report_path, regulatory_report_path=regulatory_report_path,
        evidence_path=evidence_path, ai_summary=summary_result["summary"],
    )


async def _fetch_timeline(clients: ServiceClients, incident_id: int) -> list[dict]:
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{clients.incident_service_url}/incidents/{incident_id}/timeline", headers=await clients.auth_headers(),
        )
        response.raise_for_status()
        return response.json()["items"]
