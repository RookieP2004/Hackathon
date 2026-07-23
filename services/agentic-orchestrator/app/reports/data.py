"""
Real data aggregation for every enterprise report type. Each function reads
genuinely real data (direct Postgres queries where no cross-service filter
exists yet -- e.g. no service exposes a date-ranged "incidents this week"
endpoint -- and real HTTP calls to knowledge-graph/predictive-risk-engine
where graph traversal or live fusion is actually needed) and assembles it
into a ReportContent. No field here is invented: every number traces back to
a real row or a real live computation.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import asyncpg

from app.orchestrator.clients import ServiceClients
from app.reports import charts
from app.reports.content import ReportContent, ReportSection

_SEVERITY_WEIGHT = {"critical": 15, "high": 8, "medium": 4, "low": 1}
_ALERT_SEVERITY_WEIGHT = {"critical": 3, "high": 1}
_REGULATION_CODES = ["FACTORY_ACT", "DGMS", "OISD"]


async def _plant_scope(conn: asyncpg.Connection, plant_id: int) -> tuple[list[int], list[int]]:
    zone_rows = await conn.fetch("SELECT z.id FROM zones z JOIN buildings b ON b.id = z.building_id WHERE b.plant_id = $1", plant_id)
    zone_ids = [r["id"] for r in zone_rows]
    equipment_rows = await conn.fetch("SELECT id FROM equipment WHERE zone_id = ANY($1::bigint[])", zone_ids) if zone_ids else []
    equipment_ids = [r["id"] for r in equipment_rows]
    return zone_ids, equipment_ids


def _pct_change(current: float, previous: float) -> str:
    if previous == 0:
        return "n/a (no prior period data)" if current == 0 else "new activity (no prior period baseline)"
    change = (current - previous) / previous * 100
    return f"{'+' if change >= 0 else ''}{change:.0f}% vs previous period"


async def aggregate_period_summary(postgres_dsn: str, *, plant_id: int, start: date, end: date, period_label: str) -> ReportContent:
    period_length = end - start
    prev_start, prev_end = start - period_length, start

    conn = await asyncpg.connect(postgres_dsn)
    try:
        zone_ids, equipment_ids = await _plant_scope(conn, plant_id)

        incidents = await conn.fetch(
            "SELECT id, incident_number, severity, status, opened_at FROM incidents "
            "WHERE plant_id = $1 AND opened_at >= $2 AND opened_at < $3 ORDER BY opened_at",
            plant_id, start, end,
        )
        prev_incident_count = await conn.fetchval(
            "SELECT count(*) FROM incidents WHERE plant_id = $1 AND opened_at >= $2 AND opened_at < $3", plant_id, prev_start, prev_end
        )

        alerts = await conn.fetch(
            "SELECT id, alert_type, severity, triggered_at FROM alerts "
            "WHERE (zone_id = ANY($1::bigint[]) OR equipment_id = ANY($2::bigint[])) AND triggered_at >= $3 AND triggered_at < $4 "
            "ORDER BY triggered_at",
            zone_ids, equipment_ids, start, end,
        )

        avg_risk_row = await conn.fetchrow(
            "SELECT avg(score) AS avg_score, max(score) AS max_score FROM risk_scores "
            "WHERE (zone_id = ANY($1::bigint[]) OR equipment_id = ANY($2::bigint[])) AND computed_at >= $3 AND computed_at < $4",
            zone_ids, equipment_ids, start, end,
        )
        prev_avg_risk = await conn.fetchval(
            "SELECT avg(score) FROM risk_scores WHERE (zone_id = ANY($1::bigint[]) OR equipment_id = ANY($2::bigint[])) AND computed_at >= $3 AND computed_at < $4",
            zone_ids, equipment_ids, prev_start, prev_end,
        )

        permit_violations = await conn.fetchval(
            "SELECT count(*) FROM permits WHERE (zone_id = ANY($1::bigint[]) OR equipment_id = ANY($2::bigint[])) AND status = 'active' AND valid_to < now()",
            zone_ids, equipment_ids,
        )

        maintenance_completed = await conn.fetchval(
            "SELECT count(*) FROM maintenance_records WHERE equipment_id = ANY($1::bigint[]) AND status = 'completed' AND completed_at >= $2 AND completed_at < $3",
            equipment_ids, start, end,
        )
    finally:
        await conn.close()

    severity_counts: dict[str, int] = {}
    for incident in incidents:
        severity_counts[incident["severity"]] = severity_counts.get(incident["severity"], 0) + 1

    avg_score = float(avg_risk_row["avg_score"]) if avg_risk_row["avg_score"] is not None else 0.0
    max_score = float(avg_risk_row["max_score"]) if avg_risk_row["max_score"] is not None else 0.0
    prev_avg_score = float(prev_avg_risk) if prev_avg_risk is not None else 0.0

    executive_summary = (
        f"{period_label} summary for plant {plant_id} ({start.isoformat()} to {end.isoformat()}): "
        f"{len(incidents)} incident(s) opened ({_pct_change(len(incidents), prev_incident_count or 0)}), "
        f"{len(alerts)} alert(s) triggered, average risk score {avg_score:.1f}/100 ({_pct_change(avg_score, prev_avg_score)}), "
        f"{permit_violations} permit(s) currently in violation, {maintenance_completed} maintenance job(s) completed."
    )

    sections = [
        ReportSection(
            heading="Incidents by Severity", kind="table",
            table_headers=["Severity", "Count"], table_rows=[[sev, count] for sev, count in severity_counts.items()] or [["none", 0]],
        ),
    ]
    if severity_counts:
        sections.append(ReportSection(
            heading="Incidents by Severity (chart)", kind="chart",
            chart_path=charts.bar_chart(title=f"{period_label} Incidents by Severity", labels=list(severity_counts.keys()), values=list(severity_counts.values()), ylabel="count"),
        ))
    sections.append(ReportSection(
        heading="Alerts Triggered", kind="table",
        table_headers=["Alert Type", "Severity", "Triggered At"],
        table_rows=[[a["alert_type"], a["severity"], a["triggered_at"].isoformat()] for a in alerts] or [["none", "-", "-"]],
    ))
    sections.append(ReportSection(
        heading="Risk & Compliance Snapshot", kind="table",
        table_headers=["Metric", "Value"],
        table_rows=[
            ["Average risk score", f"{avg_score:.1f}/100"], ["Peak risk score", f"{max_score:.1f}/100"],
            ["Permits in violation", str(permit_violations)], ["Maintenance completed", str(maintenance_completed)],
        ],
    ))

    recommendations = []
    if severity_counts.get("critical", 0) > 0:
        recommendations.append(f"{severity_counts['critical']} critical incident(s) opened this period -- verify root cause is documented for each before closure.")
    if permit_violations > 0:
        recommendations.append(f"{permit_violations} permit(s) are active but past expiry -- renew or close them immediately (see Permit Report).")
    if avg_score > prev_avg_score and prev_avg_score > 0:
        recommendations.append("Average risk score is trending upward vs the previous period -- prioritize inspections on the highest-scoring equipment (see Machine Health Report).")
    if not recommendations:
        recommendations.append("No elevated risk indicators this period -- maintain current inspection cadence.")

    return ReportContent(
        report_type=period_label.lower(), title=f"{period_label} Safety Report", plant_id=plant_id,
        date_range_start=start, date_range_end=end, executive_summary=executive_summary,
        sections=sections, recommendations=recommendations,
    )


async def aggregate_rca(clients: ServiceClients, postgres_dsn: str, incident_id: int, *, report_type: str = "rca") -> ReportContent:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        incident = await conn.fetchrow("SELECT * FROM incidents WHERE id = $1", incident_id)
        if incident is None:
            raise ValueError(f"No incident with id {incident_id}")
        timeline = await conn.fetch(
            "SELECT event_type, actor_type, occurred_at FROM incident_timeline_events WHERE incident_id = $1 ORDER BY occurred_at", incident_id
        )
        equipment_tag = None
        if incident["equipment_id"] is not None:
            equipment_row = await conn.fetchrow("SELECT tag FROM equipment WHERE id = $1", incident["equipment_id"])
            equipment_tag = equipment_row["tag"] if equipment_row else None
    finally:
        await conn.close()

    assessments: list[dict] = []
    if incident["equipment_id"] is not None:
        try:
            assessments = await clients.assess_equipment(incident["equipment_id"])
        except Exception:
            assessments = []
    # The incidents table doesn't persist which hazard_class triggered it (only
    # transient at assessment time) -- best-effort: the hazard with the highest
    # *current* score is the most likely match for what's still elevated now.
    top_assessment = max(assessments, key=lambda a: a["score"]) if assessments else None

    similar_incidents: list[dict] = []
    if incident["equipment_id"] is not None:
        try:
            similar_incidents = await clients.graph_similar_incidents(incident["equipment_id"], limit=5)
        except Exception:
            similar_incidents = []

    executive_summary = (
        f"Root Cause Analysis for {incident['incident_number']} ({incident['severity']}, status {incident['status']}), "
        f"opened {incident['opened_at'].isoformat()} on equipment {equipment_tag or incident['equipment_id'] or 'unassigned'}. "
        f"Root cause: {incident['root_cause'] or 'not yet documented by an investigator'}."
    )

    sections = [
        ReportSection(
            heading="Incident Timeline", kind="table", table_headers=["Event", "Actor", "Occurred At"],
            table_rows=[[t["event_type"], t["actor_type"], t["occurred_at"].isoformat()] for t in timeline],
        ),
    ]
    if top_assessment:
        sections.append(ReportSection(
            heading=f"Current Contributing Factors ({top_assessment['hazard_class']}, live re-assessment)", kind="table",
            table_headers=["Evidence Node", "Source Type", "Likelihood Ratio"],
            table_rows=[[f["evidence_node_id"], f["source_type"], f"{f['likelihood_ratio']:.2f}"] for f in top_assessment["contributing_factors"][:6]],
        ))
    sections.append(ReportSection(
        heading="Similar Historical Incidents (topological similarity)", kind="table",
        table_headers=["Incident", "Equipment", "Severity", "Root Cause"],
        table_rows=[[i.get("incidentNumber"), i.get("equipmentTag"), i.get("severity"), i.get("rootCause") or "not documented"] for i in similar_incidents]
        or [["none found", "-", "-", "-"]],
    ))

    recommendations = list(top_assessment["recommendations"]) if top_assessment else []
    if not incident["root_cause"]:
        recommendations.append("Root cause is not yet documented -- assign an investigator before closing this incident.")
    if not recommendations:
        recommendations.append("No further automated recommendations -- rely on investigator findings.")

    title_prefix = "Root Cause Analysis" if report_type == "rca" else "Incident Report"
    return ReportContent(
        report_type=report_type, title=f"{title_prefix} -- {incident['incident_number']}", plant_id=incident["plant_id"],
        date_range_start=incident["opened_at"].date(), date_range_end=(incident["closed_at"] or datetime.now(timezone.utc)).date(),
        executive_summary=executive_summary, sections=sections, recommendations=recommendations,
    )


async def aggregate_compliance(clients: ServiceClients, postgres_dsn: str, plant_id: int) -> ReportContent:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        zone_ids, equipment_ids = await _plant_scope(conn, plant_id)
        permit_rows = await conn.fetch(
            """
            SELECT p.permit_number, p.valid_to, e.tag AS equipment_tag, z.name AS zone_name
            FROM permits p LEFT JOIN equipment e ON e.id = p.equipment_id LEFT JOIN zones z ON z.id = p.zone_id
            WHERE (p.zone_id = ANY($1::bigint[]) OR p.equipment_id = ANY($2::bigint[])) AND p.status = 'active' AND p.valid_to < now()
            ORDER BY p.valid_to
            """,
            zone_ids, equipment_ids,
        )
    finally:
        await conn.close()

    gaps_by_regulation: dict[str, list[dict]] = {}
    for code in _REGULATION_CODES:
        try:
            gaps_by_regulation[code] = await clients.graph_compliance_gaps(code)
        except Exception:
            gaps_by_regulation[code] = []

    now = datetime.now(timezone.utc)
    executive_summary = (
        f"Compliance snapshot for plant {plant_id}: {len(permit_rows)} permit(s) active past expiry; "
        f"{sum(len(g) for g in gaps_by_regulation.values())} equipment/regulation compliance gap(s) detected across "
        f"{len(_REGULATION_CODES)} tracked regulations ({', '.join(_REGULATION_CODES)})."
    )

    sections = [
        ReportSection(
            heading="Expired-But-Active Permits", kind="table",
            table_headers=["Permit", "Target", "Expired"],
            table_rows=[[p["permit_number"], p["equipment_tag"] or p["zone_name"] or "unassigned", f"{(now - p['valid_to']).days} day(s) ago"] for p in permit_rows]
            or [["none", "-", "-"]],
        ),
    ]
    for code, gaps in gaps_by_regulation.items():
        sections.append(ReportSection(
            heading=f"Compliance Gaps -- {code}", kind="table",
            table_headers=["Equipment", "Last Serviced"],
            table_rows=[[g.get("equipmentTag") or g.get("equipmentName"), str(g.get("lastServiced") or "never")] for g in gaps] or [["none", "-"]],
        ))

    recommendations = []
    if permit_rows:
        recommendations.append(f"Renew or close {len(permit_rows)} expired-but-active permit(s) immediately.")
    for code, gaps in gaps_by_regulation.items():
        if gaps:
            recommendations.append(f"{len(gaps)} equipment item(s) are overdue for {code}-mandated servicing -- schedule maintenance.")
    if not recommendations:
        recommendations.append("No compliance gaps detected against the tracked regulation set.")

    return ReportContent(
        report_type="compliance", title="Compliance Report", plant_id=plant_id,
        date_range_start=now.date(), date_range_end=now.date(), executive_summary=executive_summary,
        sections=sections, recommendations=recommendations,
    )


async def compute_safety_score(postgres_dsn: str, *, plant_id: int, start: date, end: date) -> ReportContent:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        zone_ids, equipment_ids = await _plant_scope(conn, plant_id)
        incident_rows = await conn.fetch(
            "SELECT severity, count(*) AS n FROM incidents WHERE plant_id = $1 AND opened_at >= $2 AND opened_at < $3 GROUP BY severity",
            plant_id, start, end,
        )
        alert_rows = await conn.fetch(
            "SELECT severity, count(*) AS n FROM alerts WHERE (zone_id = ANY($1::bigint[]) OR equipment_id = ANY($2::bigint[])) AND triggered_at >= $3 AND triggered_at < $4 GROUP BY severity",
            zone_ids, equipment_ids, start, end,
        )
        permit_violations = await conn.fetchval(
            "SELECT count(*) FROM permits WHERE (zone_id = ANY($1::bigint[]) OR equipment_id = ANY($2::bigint[])) AND status = 'active' AND valid_to < now()",
            zone_ids, equipment_ids,
        )
        avg_score = await conn.fetchval(
            "SELECT avg(score) FROM risk_scores WHERE (zone_id = ANY($1::bigint[]) OR equipment_id = ANY($2::bigint[])) AND computed_at >= $3 AND computed_at < $4",
            zone_ids, equipment_ids, start, end,
        )
    finally:
        await conn.close()

    incident_penalty = min(60, sum(_SEVERITY_WEIGHT.get(r["severity"], 1) * r["n"] for r in incident_rows))
    alert_penalty = min(20, sum(_ALERT_SEVERITY_WEIGHT.get(r["severity"], 0) * r["n"] for r in alert_rows))
    permit_penalty = min(20, permit_violations * 5)
    risk_penalty = min(20, float(avg_score or 0.0) * 0.2)
    total_penalty = min(100, incident_penalty + alert_penalty + permit_penalty + risk_penalty)
    safety_score = round(100 - total_penalty, 1)

    executive_summary = (
        f"Safety score for plant {plant_id} ({start.isoformat()} to {end.isoformat()}): {safety_score}/100. "
        f"Computed transparently from a weighted composite: incident severity ({incident_penalty:.1f} pt penalty), "
        f"alert frequency ({alert_penalty:.1f} pt), permit compliance ({permit_penalty:.1f} pt), and average risk score "
        f"({risk_penalty:.1f} pt) -- every component shown below, not a black-box number."
    )

    breakdown = {
        "Incident severity penalty": incident_penalty, "Alert frequency penalty": alert_penalty,
        "Permit violation penalty": permit_penalty, "Average risk score penalty": risk_penalty,
    }
    sections = [
        ReportSection(heading="Safety Score Breakdown", kind="table", table_headers=["Component", "Penalty (of 100)"], table_rows=[[k, f"{v:.1f}"] for k, v in breakdown.items()]),
        ReportSection(heading="Penalty Breakdown (chart)", kind="chart", chart_path=charts.pie_chart(title="Safety Score Penalty Breakdown", labels=list(breakdown.keys()), values=[max(0.01, v) for v in breakdown.values()])),
    ]

    recommendations = []
    worst_component = max(breakdown, key=breakdown.get)
    if breakdown[worst_component] > 0:
        recommendations.append(f"Largest safety-score drag this period: {worst_component.lower()} -- address this first to raise the score fastest.")
    else:
        recommendations.append("No safety-score penalties recorded this period -- maintain current practices.")

    return ReportContent(
        report_type="safety_score", title="Safety Score Report", plant_id=plant_id,
        date_range_start=start, date_range_end=end, executive_summary=executive_summary,
        sections=sections, recommendations=recommendations,
    )


async def aggregate_machine_health(postgres_dsn: str, plant_id: int) -> ReportContent:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        zone_ids, _ = await _plant_scope(conn, plant_id)
        equipment_rows = await conn.fetch(
            "SELECT id, tag, name, status, criticality FROM equipment WHERE zone_id = ANY($1::bigint[]) ORDER BY criticality DESC", zone_ids
        )
        equipment_ids = [e["id"] for e in equipment_rows]
        open_maintenance = await conn.fetch(
            "SELECT equipment_id, count(*) AS n FROM maintenance_records WHERE equipment_id = ANY($1::bigint[]) AND status IN ('scheduled','in_progress') GROUP BY equipment_id",
            equipment_ids,
        )
        # The sensor simulator's fusion loop continuously computes and persists a
        # risk_scores row per hazard class every tick -- reading the max score from
        # the last 15 minutes' worth of ticks is a real, already-computed snapshot,
        # far cheaper than forcing a fresh live Bayesian re-assessment for every
        # piece of equipment in the plant (this plant alone has 40).
        latest_scores = await conn.fetch(
            "SELECT equipment_id, max(score) AS top_score FROM risk_scores WHERE equipment_id = ANY($1::bigint[]) AND computed_at > now() - interval '15 minutes' GROUP BY equipment_id",
            equipment_ids,
        )
    finally:
        await conn.close()

    open_maintenance_by_equipment = {r["equipment_id"]: r["n"] for r in open_maintenance}
    latest_score_by_equipment = {r["equipment_id"]: float(r["top_score"]) for r in latest_scores}

    equipment_health = []
    for equipment in equipment_rows:
        equipment_health.append({
            "tag": equipment["tag"], "name": equipment["name"], "status": equipment["status"],
            "criticality": equipment["criticality"], "top_risk_score": latest_score_by_equipment.get(equipment["id"]),
            "open_maintenance": open_maintenance_by_equipment.get(equipment["id"], 0),
        })

    executive_summary = (
        f"Machine health snapshot for plant {plant_id}: {len(equipment_health)} equipment item(s) tracked, "
        f"{sum(1 for e in equipment_health if e['open_maintenance'] > 0)} with open maintenance work orders."
    )

    sections = [
        ReportSection(
            heading="Equipment Health", kind="table",
            table_headers=["Tag", "Name", "Status", "Criticality", "Top Risk Score", "Open Maintenance"],
            table_rows=[[e["tag"], e["name"], e["status"], e["criticality"], f"{e['top_risk_score']:.1f}" if e["top_risk_score"] is not None else "n/a", e["open_maintenance"]] for e in equipment_health],
        ),
    ]
    scored = [e for e in equipment_health if e["top_risk_score"] is not None]
    if scored:
        sections.append(ReportSection(
            heading="Top Risk Score by Equipment (chart)", kind="chart",
            chart_path=charts.bar_chart(title="Top Risk Score by Equipment", labels=[e["tag"] for e in scored], values=[e["top_risk_score"] for e in scored], ylabel="score /100"),
        ))

    recommendations = []
    for e in equipment_health:
        if e["top_risk_score"] is not None and e["top_risk_score"] >= 60:
            recommendations.append(f"{e['tag']} has an elevated risk score ({e['top_risk_score']:.1f}/100) -- prioritize inspection.")
        if e["open_maintenance"] > 0 and e["criticality"] <= 2:
            recommendations.append(f"{e['tag']} is high-criticality with {e['open_maintenance']} open maintenance job(s) -- expedite.")
    if not recommendations:
        recommendations.append("No equipment currently shows elevated risk or overdue maintenance.")

    return ReportContent(
        report_type="machine_health", title="Machine Health Report", plant_id=plant_id,
        date_range_start=datetime.now(timezone.utc).date(), date_range_end=datetime.now(timezone.utc).date(), executive_summary=executive_summary,
        sections=sections, recommendations=recommendations,
    )


async def aggregate_worker_safety(clients: ServiceClients, postgres_dsn: str, plant_id: int) -> ReportContent:
    try:
        exposed_workers = await clients.graph_worker_exposure(min_score=70, within_minutes=1440)
    except Exception:
        exposed_workers = []

    conn = await asyncpg.connect(postgres_dsn)
    try:
        # incidents don't persist hazard_class directly (only transient at
        # assessment time) -- the AI-generated summary literally narrates
        # "<hazard> risk" per app/orchestrator/summary.py's template, so this
        # is an honest text-search proxy for "worker_injury"-flagged incidents,
        # not a fabricated join.
        worker_injury_incidents = await conn.fetch(
            "SELECT incident_number, severity, status, opened_at FROM incidents WHERE plant_id = $1 AND ai_generated_summary ILIKE '%worker injury%' ORDER BY opened_at DESC",
            plant_id,
        )
        active_permit_count = await conn.fetchval(
            "SELECT count(DISTINCT worker_id) FROM permits p JOIN zones z ON z.id = p.zone_id JOIN buildings b ON b.id = z.building_id WHERE b.plant_id = $1 AND p.status = 'active'",
            plant_id,
        )
    finally:
        await conn.close()

    executive_summary = (
        f"Worker safety snapshot for plant {plant_id}: {len(exposed_workers)} worker(s) currently in a zone above the "
        f"risk threshold, {len(worker_injury_incidents)} worker-injury-flagged incident(s) on record, "
        f"{active_permit_count} worker(s) currently holding an active permit."
    )

    sections = [
        ReportSection(
            heading="Workers Currently in Elevated-Risk Zones", kind="table",
            table_headers=["Worker", "Badge", "Zone", "Hazard", "Zone Risk Score"],
            table_rows=[[w.get("workerName"), w.get("badgeId"), w.get("zoneName"), w.get("hazardClass"), w.get("score")] for w in exposed_workers]
            or [["none currently exposed", "-", "-", "-", "-"]],
        ),
        ReportSection(
            heading="Worker-Injury-Flagged Incidents", kind="table",
            table_headers=["Incident", "Severity", "Status", "Opened"],
            table_rows=[[i["incident_number"], i["severity"], i["status"], i["opened_at"].isoformat()] for i in worker_injury_incidents] or [["none", "-", "-", "-"]],
        ),
    ]

    recommendations = []
    if exposed_workers:
        recommendations.append(f"{len(exposed_workers)} worker(s) are currently in a zone above the risk threshold -- verify evacuation/PPE protocols are active.")
    if worker_injury_incidents:
        recommendations.append(f"{len(worker_injury_incidents)} worker-injury incident(s) on record -- review PPE compliance and permit conditions for the affected zones.")
    if not recommendations:
        recommendations.append("No elevated worker-exposure risk detected currently.")

    return ReportContent(
        report_type="worker_safety", title="Worker Safety Report", plant_id=plant_id,
        date_range_start=datetime.now(timezone.utc).date(), date_range_end=datetime.now(timezone.utc).date(), executive_summary=executive_summary,
        sections=sections, recommendations=recommendations,
    )


async def aggregate_permit_report(postgres_dsn: str, *, plant_id: int, start: date, end: date) -> ReportContent:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        zone_ids, equipment_ids = await _plant_scope(conn, plant_id)
        issued = await conn.fetch(
            """
            SELECT p.permit_number, pt.name AS permit_type, p.status, p.valid_from, p.valid_to
            FROM permits p JOIN permit_types pt ON pt.id = p.permit_type_id
            WHERE (p.zone_id = ANY($1::bigint[]) OR p.equipment_id = ANY($2::bigint[])) AND p.created_at >= $3 AND p.created_at < $4
            ORDER BY p.created_at
            """,
            zone_ids, equipment_ids, start, end,
        )
        violations = await conn.fetch(
            "SELECT permit_number, valid_to FROM permits WHERE (zone_id = ANY($1::bigint[]) OR equipment_id = ANY($2::bigint[])) AND status = 'active' AND valid_to < now()",
            zone_ids, equipment_ids,
        )
        by_type = await conn.fetch(
            """
            SELECT pt.name AS permit_type, count(*) AS n FROM permits p JOIN permit_types pt ON pt.id = p.permit_type_id
            WHERE (p.zone_id = ANY($1::bigint[]) OR p.equipment_id = ANY($2::bigint[]))
            GROUP BY pt.name
            """,
            zone_ids, equipment_ids,
        )
    finally:
        await conn.close()

    executive_summary = (
        f"Permit report for plant {plant_id} ({start.isoformat()} to {end.isoformat()}): {len(issued)} permit(s) issued, "
        f"{len(violations)} currently in violation (active but expired)."
    )

    sections = [
        ReportSection(
            heading="Permits Issued This Period", kind="table",
            table_headers=["Permit", "Type", "Status", "Valid From", "Valid To"],
            table_rows=[[p["permit_number"], p["permit_type"], p["status"], p["valid_from"].isoformat(), p["valid_to"].isoformat()] for p in issued] or [["none", "-", "-", "-", "-"]],
        ),
        ReportSection(
            heading="Currently in Violation", kind="table",
            table_headers=["Permit", "Expired"], table_rows=[[v["permit_number"], v["valid_to"].isoformat()] for v in violations] or [["none", "-"]],
        ),
    ]
    if by_type:
        sections.append(ReportSection(
            heading="Permits by Type (chart)", kind="chart",
            chart_path=charts.bar_chart(title="Permits by Type (all-time, this scope)", labels=[r["permit_type"] for r in by_type], values=[r["n"] for r in by_type], ylabel="count"),
        ))

    recommendations = [f"Renew or close {len(violations)} expired-but-active permit(s) immediately."] if violations else ["No permit violations -- maintain current renewal cadence."]

    return ReportContent(
        report_type="permit", title="Permit Report", plant_id=plant_id,
        date_range_start=start, date_range_end=end, executive_summary=executive_summary,
        sections=sections, recommendations=recommendations,
    )


async def aggregate_maintenance_report(postgres_dsn: str, *, plant_id: int, start: date, end: date) -> ReportContent:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        _, equipment_ids = await _plant_scope(conn, plant_id)
        records = await conn.fetch(
            """
            SELECT m.status, mt.name AS maintenance_type, e.tag AS equipment_tag, m.scheduled_date, m.completed_at, m.cost
            FROM maintenance_records m JOIN maintenance_types mt ON mt.id = m.maintenance_type_id JOIN equipment e ON e.id = m.equipment_id
            WHERE m.equipment_id = ANY($1::bigint[]) AND m.created_at >= $2 AND m.created_at < $3
            ORDER BY m.created_at
            """,
            equipment_ids, start, end,
        )
        overdue = await conn.fetch(
            "SELECT m.id, e.tag AS equipment_tag, m.scheduled_date FROM maintenance_records m JOIN equipment e ON e.id = m.equipment_id "
            "WHERE m.equipment_id = ANY($1::bigint[]) AND m.status = 'scheduled' AND m.scheduled_date < now()::date",
            equipment_ids,
        )
    finally:
        await conn.close()

    status_counts: dict[str, int] = {}
    total_cost = 0.0
    for r in records:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        total_cost += float(r["cost"] or 0)

    executive_summary = (
        f"Maintenance report for plant {plant_id} ({start.isoformat()} to {end.isoformat()}): {len(records)} work order(s) "
        f"({', '.join(f'{k}: {v}' for k, v in status_counts.items()) or 'none'}), total recorded cost {total_cost:.2f}, "
        f"{len(overdue)} job(s) overdue."
    )

    sections = [
        ReportSection(
            heading="Maintenance Work Orders", kind="table",
            table_headers=["Equipment", "Type", "Status", "Scheduled", "Completed", "Cost"],
            table_rows=[[r["equipment_tag"], r["maintenance_type"], r["status"], str(r["scheduled_date"] or "-"), str(r["completed_at"] or "-"), r["cost"] or 0] for r in records]
            or [["none", "-", "-", "-", "-", "-"]],
        ),
        ReportSection(
            heading="Overdue Work Orders", kind="table",
            table_headers=["Equipment", "Scheduled Date"], table_rows=[[o["equipment_tag"], str(o["scheduled_date"])] for o in overdue] or [["none", "-"]],
        ),
    ]
    if status_counts:
        sections.append(ReportSection(
            heading="Work Orders by Status (chart)", kind="chart",
            chart_path=charts.bar_chart(title="Maintenance Work Orders by Status", labels=list(status_counts.keys()), values=list(status_counts.values()), ylabel="count"),
        ))

    recommendations = [f"{len(overdue)} maintenance job(s) are overdue -- reschedule or expedite."] if overdue else ["No overdue maintenance -- schedule adherence is on track."]

    return ReportContent(
        report_type="maintenance", title="Maintenance Report", plant_id=plant_id,
        date_range_start=start, date_range_end=end, executive_summary=executive_summary,
        sections=sections, recommendations=recommendations,
    )
