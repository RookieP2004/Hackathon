"""
Generate Report + Create Regulatory Report — real PDF files (fpdf2, no
heavy native deps), written to disk with a real, retrievable file path set
as the Report record's `file_url`. Professional layout/branding polish
(charts, executive summaries, multi-format export) is the Enterprise Reports
pass's job; this pass's job is a genuine, complete, correctly-structured PDF
generated automatically the moment a critical incident opens -- not a
placeholder string.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.pdf_text import sanitize_for_pdf

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "generated_reports" / "incidents"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

INSPECTIONS_DIR = Path(__file__).resolve().parent.parent.parent / "generated_reports" / "inspections"
INSPECTIONS_DIR.mkdir(parents=True, exist_ok=True)


class _ReportPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "AEGIS AI -- Automated Emergency Response Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def section_title(self, title: str) -> None:
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 8, sanitize_for_pdf(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.ln(2)

    def body_text(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5, sanitize_for_pdf(text))
        self.ln(2)


def generate_incident_report(
    *, incident_id: int, incident_number: str, hazard_class: str, equipment_tag: str, zone_id: int | None,
    score: float, severity: str, confidence: float, contributing_factors: list[dict], recommendations: list[str],
    ai_summary: str, timeline_events: list[dict],
) -> str:
    pdf = _ReportPDF()
    pdf.add_page()

    pdf.section_title(f"Incident {incident_number} (id {incident_id})")
    pdf.body_text(
        f"Hazard class: {hazard_class}\nEquipment: {equipment_tag}\nZone: {zone_id or 'n/a'}\n"
        f"Risk score: {score:.1f}/100  |  Severity: {severity}  |  Confidence: {confidence:.0%}"
    )

    pdf.section_title("AI-Generated Summary")
    pdf.body_text(ai_summary)

    pdf.section_title("Contributing Factors (ranked by evidentiary weight)")
    for factor in contributing_factors[:6]:
        pdf.body_text(f"- {factor['source_type']}:{factor['evidence_node_id']}  (likelihood ratio {factor['likelihood_ratio']:.2f})  refs: {', '.join(factor['evidence_refs'])}")

    pdf.section_title("Recommendations")
    for rec in recommendations:
        pdf.body_text(f"- {rec}")

    pdf.section_title("Response Timeline")
    for event in timeline_events:
        pdf.body_text(f"- [{event.get('occurred_at', '')}] {event.get('event_type', '')}")

    file_path = REPORTS_DIR / f"incident-{incident_id}-report.pdf"
    pdf.output(str(file_path))
    return str(file_path)


def generate_regulatory_report(
    *, incident_id: int, incident_number: str, hazard_class: str, equipment_tag: str, zone_id: int | None,
    score: float, severity: str, citations: list[str], sensor_snapshot: dict,
) -> str:
    pdf = _ReportPDF()
    pdf.add_page()

    pdf.section_title(f"Regulatory Notification -- Incident {incident_number}")
    pdf.body_text(
        f"This report documents an automated safety incident opened under AEGIS AI's continuous monitoring system, "
        f"for regulatory submission and audit-trail purposes.\n\n"
        f"Hazard class: {hazard_class}\nEquipment: {equipment_tag}\nZone: {zone_id or 'n/a'}\n"
        f"Risk score at time of opening: {score:.1f}/100 ({severity})"
    )

    pdf.section_title("Governing Regulations / Standards Cited")
    if citations:
        for citation in citations:
            pdf.body_text(f"- {citation}")
    else:
        pdf.body_text("No governing regulation could be retrieved above the minimum confidence threshold for this hazard class -- flagged as a corpus gap for Safety Officer review.")

    pdf.section_title("Captured Sensor Evidence at Time of Incident")
    for sensor in sensor_snapshot.get("sensors", [])[:5]:
        latest = sensor["readings"][-1] if sensor["readings"] else None
        latest_str = f"{latest['value']} {sensor['unit']} at {latest['recorded_at']}" if latest else "no readings captured"
        pdf.body_text(f"- {sensor['tag']} ({sensor['sensor_type']}): {latest_str}")

    file_path = REPORTS_DIR / f"incident-{incident_id}-regulatory-report.pdf"
    pdf.output(str(file_path))
    return str(file_path)


def generate_inspection_report(
    *, equipment_id: int, equipment_tag: str, zone_id: int | None, assessments: list[dict],
    maintenance_records: list[dict], recent_incidents: list[dict], sensor_snapshot: dict,
) -> str:
    pdf = _ReportPDF()
    pdf.add_page()

    pdf.section_title(f"Inspection Report -- {equipment_tag} (equipment id {equipment_id})")
    pdf.body_text(f"Zone: {zone_id or 'n/a'}")

    pdf.section_title("Current Risk Assessment (all hazard classes, live Bayesian Risk Fusion Engine)")
    for assessment in assessments:
        pdf.body_text(
            f"- {assessment['hazard_class']}: score {assessment['score']:.1f}/100, "
            f"severity {assessment['severity']}, confidence {assessment['confidence_scalar']:.0%}"
        )

    pdf.section_title("Recent Sensor Readings")
    sensors = sensor_snapshot.get("sensors", [])
    if sensors:
        for sensor in sensors[:8]:
            latest = sensor["readings"][-1] if sensor["readings"] else None
            latest_str = f"{latest['value']} {sensor['unit']} at {latest['recorded_at']}" if latest else "no readings captured"
            pdf.body_text(f"- {sensor['tag']} ({sensor['sensor_type']}): {latest_str}")
    else:
        pdf.body_text("No sensors are mapped to this equipment.")

    pdf.section_title("Maintenance History")
    if maintenance_records:
        for record in maintenance_records[:8]:
            pdf.body_text(f"- [{record['status']}] {record['description']} (scheduled {record.get('scheduled_date') or 'n/a'})")
    else:
        pdf.body_text("No maintenance records found for this equipment.")

    pdf.section_title("Recent Incidents")
    if recent_incidents:
        for incident in recent_incidents[:8]:
            pdf.body_text(f"- {incident['incident_number']} ({incident['severity']}, {incident['status']}) opened {incident['opened_at']}")
    else:
        pdf.body_text("No incidents recorded for this equipment.")

    file_path = INSPECTIONS_DIR / f"inspection-{equipment_id}-{int(datetime.now(timezone.utc).timestamp())}.pdf"
    pdf.output(str(file_path))
    return str(file_path)
