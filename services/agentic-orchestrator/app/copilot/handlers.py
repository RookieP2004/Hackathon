"""
One handler per Copilot intent. Every handler is a thin composition over
already-real backend calls (incident-service, notification-service,
predictive-risk-engine, knowledge-graph, rag-service, and direct Postgres
reads where no endpoint yet exists) -- no handler here fabricates data or
calls an LLM that isn't deployed in this environment. Each returns
{"answer": str, "citations": list[str], "data": dict} so the router can
render a grounded, cited response.
"""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg

from app.orchestrator.clients import ServiceClients
from app.orchestrator.evidence import capture_sensor_data
from app.orchestrator.reports import generate_inspection_report
from app.orchestrator.summary import generate_ai_summary


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 3600:
        return f"{seconds / 60:.0f} minutes"
    if seconds < 86400:
        return f"{seconds / 3600:.1f} hours"
    return f"{seconds / 86400:.1f} days"


async def handle_current_state(clients: ServiceClients) -> dict:
    incidents = await clients.list_incidents(status="open", page_size=10)
    alerts = await clients.list_alerts(status="open", page_size=10)
    risk_scores = await clients.list_risk_scores(page_size=10)

    lines = []
    citations = []

    if incidents:
        lines.append(f"{len(incidents)} open incident(s):")
        for incident in incidents[:5]:
            lines.append(f"  - {incident['incident_number']} ({incident['severity']}, equipment {incident.get('equipment_id')})")
            citations.append(f"incident:{incident['id']}")
    else:
        lines.append("No open incidents.")

    if alerts:
        lines.append(f"{len(alerts)} open alert(s):")
        for alert in alerts[:5]:
            lines.append(f"  - {alert['alert_type']} ({alert['severity']}): {alert['message']}")
            citations.append(f"alert:{alert['id']}")
    else:
        lines.append("No open alerts.")

    if risk_scores:
        top = max(risk_scores, key=lambda r: r["score"])
        lines.append(f"Highest recent risk score: {top['score']:.1f}/100 on equipment {top.get('equipment_id')} (computed {top['computed_at']}).")
        citations.append(f"risk_score:{top['id']}")
    else:
        lines.append("No risk scores computed recently.")

    return {"answer": "\n".join(lines), "citations": citations, "data": {"incidents": incidents, "alerts": alerts, "risk_scores": risk_scores}}


async def handle_why_risk_increasing(clients: ServiceClients, equipment: dict | None, hazard_class: str | None) -> dict:
    if equipment is None:
        return {
            "answer": "Which equipment are you asking about? I couldn't identify one in your question -- try mentioning its tag (e.g. \"V-12\") or name.",
            "citations": [], "data": {},
        }

    assessments = await clients.assess_equipment(equipment["equipment_id"])
    if not assessments:
        return {"answer": f"No risk assessment is currently available for {equipment['tag']}.", "citations": [], "data": {}}

    assessment = next((a for a in assessments if a["hazard_class"] == hazard_class), None) if hazard_class else None
    if assessment is None:
        assessment = max(assessments, key=lambda a: a["score"])

    result = await generate_ai_summary(
        clients, hazard_class=assessment["hazard_class"], equipment_tag=equipment["tag"],
        score=assessment["score"], confidence=assessment["confidence_scalar"],
        top_contributing_factors=assessment["contributing_factors"],
        counterfactual=assessment["counterfactuals"][0] if assessment["counterfactuals"] else None,
    )
    return {"answer": result["summary"], "citations": result["citations"], "data": {"assessment": assessment}}


async def handle_machine_history(clients: ServiceClients, postgres_dsn: str, equipment: dict | None) -> dict:
    if equipment is None:
        return {"answer": "Which machine? I couldn't identify one in your question -- try mentioning its tag or name.", "citations": [], "data": {}}

    equipment_id = equipment["equipment_id"]
    maintenance_records = await clients.list_maintenance(equipment_id=equipment_id, page_size=5)
    incidents = await clients.list_incidents(equipment_id=equipment_id, page_size=5)
    sensor_snapshot = await capture_sensor_data(postgres_dsn, equipment_id)

    lines = [f"History for {equipment['tag']} ({equipment['name']}):"]
    citations = []

    lines.append(f"Maintenance ({len(maintenance_records)} recent record(s)):")
    for record in maintenance_records:
        lines.append(f"  - [{record['status']}] {record['description']}")
        citations.append(f"maintenance:{record['id']}")
    if not maintenance_records:
        lines.append("  - none on record")

    lines.append(f"Incidents ({len(incidents)} recent):")
    for incident in incidents:
        lines.append(f"  - {incident['incident_number']} ({incident['severity']}, {incident['status']})")
        citations.append(f"incident:{incident['id']}")
    if not incidents:
        lines.append("  - none on record")

    sensors = sensor_snapshot.get("sensors", [])
    lines.append(f"Currently mapped sensors: {len(sensors)}")
    for sensor in sensors[:5]:
        latest = sensor["readings"][-1] if sensor["readings"] else None
        lines.append(f"  - {sensor['tag']}: {latest['value'] if latest else 'no reading'} {sensor['unit']}")

    return {
        "answer": "\n".join(lines), "citations": citations,
        "data": {"maintenance": maintenance_records, "incidents": incidents, "sensor_snapshot": sensor_snapshot},
    }


async def handle_predict_failures(clients: ServiceClients, equipment: dict | None) -> dict:
    if equipment is not None:
        assessments = await clients.assess_equipment(equipment["equipment_id"])
        lines = [f"Time-to-event estimates for {equipment['tag']} (live Risk Fusion Engine, all hazard classes):"]
        citations = []
        for assessment in sorted(assessments, key=lambda a: a["score"], reverse=True):
            lines.append(
                f"  - {assessment['hazard_class']}: score {assessment['score']:.1f}/100, "
                f"estimated time to event {_format_duration(assessment.get('time_to_event_seconds'))}"
            )
        predictions = await clients.list_predictions(equipment_id=equipment["equipment_id"], page_size=5)
        if predictions:
            lines.append("Historical model-tracked predictions:")
            for prediction in predictions:
                lines.append(f"  - {prediction['model_name']}: {prediction['target_metric']} = {prediction['predicted_value']:.2f} (confidence {prediction['confidence']:.0%})")
                citations.append(f"prediction:{prediction['id']}")
        return {"answer": "\n".join(lines), "citations": citations, "data": {"assessments": assessments, "predictions": predictions}}

    predictions = await clients.list_predictions(page_size=10)
    if not predictions:
        return {"answer": "No failure predictions have been recorded yet.", "citations": [], "data": {}}
    lines = ["Most recent model-tracked failure predictions across all equipment:"]
    citations = []
    for prediction in predictions:
        lines.append(f"  - equipment {prediction['equipment_id']}: {prediction['target_metric']} = {prediction['predicted_value']:.2f} (confidence {prediction['confidence']:.0%})")
        citations.append(f"prediction:{prediction['id']}")
    return {"answer": "\n".join(lines), "citations": citations, "data": {"predictions": predictions}}


async def handle_permit_violations(postgres_dsn: str) -> dict:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT p.id, p.permit_number, p.valid_to, p.equipment_id, p.zone_id, e.tag AS equipment_tag, z.name AS zone_name
            FROM permits p
            LEFT JOIN equipment e ON e.id = p.equipment_id
            LEFT JOIN zones z ON z.id = p.zone_id
            WHERE p.status = 'active' AND p.valid_to < now()
            ORDER BY p.valid_to ASC
            """
        )
    finally:
        await conn.close()

    if not rows:
        return {"answer": "No permit violations: every active permit is within its valid window.", "citations": [], "data": {"permits": []}}

    now = datetime.now(timezone.utc)
    lines = [f"{len(rows)} permit(s) are currently active but past their expiry date:"]
    citations = []
    for row in rows:
        overdue = now - row["valid_to"]
        target = row["equipment_tag"] or row["zone_name"] or "unassigned"
        lines.append(f"  - {row['permit_number']} on {target}, expired {overdue.days} day(s) ago (valid_to {row['valid_to'].isoformat()})")
        citations.append(f"permit:{row['id']}")

    return {
        "answer": "\n".join(lines), "citations": citations,
        "data": {"permits": [dict(row) for row in rows]},
    }


async def handle_generate_inspection_report(clients: ServiceClients, postgres_dsn: str, equipment: dict | None) -> dict:
    if equipment is None:
        return {"answer": "Which equipment should the inspection report cover? I couldn't identify one in your question.", "citations": [], "data": {}}

    equipment_id = equipment["equipment_id"]
    assessments = await clients.assess_equipment(equipment_id)
    maintenance_records = await clients.list_maintenance(equipment_id=equipment_id, page_size=10)
    incidents = await clients.list_incidents(equipment_id=equipment_id, page_size=10)
    sensor_snapshot = await capture_sensor_data(postgres_dsn, equipment_id)

    file_path = generate_inspection_report(
        equipment_id=equipment_id, equipment_tag=equipment["tag"], zone_id=equipment["zone_id"],
        assessments=assessments, maintenance_records=maintenance_records, recent_incidents=incidents,
        sensor_snapshot=sensor_snapshot,
    )

    report = await clients.create_report(report_type="inspection", plant_id=None, parameters={"equipment_id": equipment_id, "equipment_tag": equipment["tag"]})
    await clients.complete_report(report["id"], file_url=file_path)

    return {
        "answer": f"Inspection report generated for {equipment['tag']}: {file_path}",
        "citations": [f"report:{report['id']}"],
        "data": {"file_path": file_path, "report_id": report["id"]},
    }


async def handle_similar_incidents(clients: ServiceClients, equipment: dict | None) -> dict:
    if equipment is None:
        return {"answer": "Similar to which equipment's incidents? I couldn't identify one in your question.", "citations": [], "data": {}}

    incidents = await clients.graph_similar_incidents(equipment["equipment_id"], limit=5)
    if not incidents:
        return {"answer": f"No topologically similar incidents were found for {equipment['tag']}.", "citations": [], "data": {"incidents": []}}

    lines = [f"Incidents with a similar topological role to {equipment['tag']}:"]
    citations = []
    for incident in incidents:
        lines.append(f"  - {incident.get('incidentNumber')} on {incident.get('equipmentTag')} ({incident.get('severity')}): {incident.get('rootCause') or 'root cause not recorded'}")
        if incident.get("incidentNumber"):
            citations.append(f"incident:{incident['incidentNumber']}")

    return {"answer": "\n".join(lines), "citations": citations, "data": {"incidents": incidents}}


async def handle_explain_regulation(clients: ServiceClients, query: str) -> dict:
    result = await clients.query_knowledge(query)
    if result.get("refused") or not result.get("chunks"):
        return {
            "answer": f"No governing regulation could be retrieved above the minimum confidence threshold ({result.get('reason', 'no matching corpus entry')}).",
            "citations": [], "data": result,
        }

    citations = [chunk["citation"] for chunk in result["chunks"][:3]]
    lines = ["Relevant governing procedure/regulation (retrieved, cited):"]
    for chunk in result["chunks"][:3]:
        lines.append(f"- {chunk['citation']}: {chunk['text'][:280]}")
    if result.get("conflicts"):
        lines.append(f"\nNote: {len(result['conflicts'])} numeric conflict(s) were detected across retrieved sources -- review before relying on a single figure.")

    return {"answer": "\n".join(lines), "citations": citations, "data": result}
