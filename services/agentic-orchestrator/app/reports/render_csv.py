"""
Renders any ReportContent into a real .csv file -- one block per table
section (each preceded by its own heading and header row), the simplest
export format for pulling this data into another tool.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone

from app.reports.content import ReportContent
from app.reports.render_pdf import REPORTS_DIR as PDF_DIR

REPORTS_DIR = PDF_DIR.parent / "enterprise"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_cell(value):
    """Excel/Sheets treats a cell starting with =, +, -, or @ as a formula to
    evaluate on open -- a report built from free-text fields (an incident's
    root_cause, a permit's conditions) could otherwise carry an attacker's
    formula straight into a report a real user opens and trusts (CWE-1236).
    Prefixing with a bare quote neutralizes it without changing what a human
    reader sees."""
    if isinstance(value, str) and value.startswith(_FORMULA_TRIGGER_CHARS):
        return "'" + value
    return value


def render_csv(content: ReportContent) -> str:
    file_path = REPORTS_DIR / f"{content.report_type}-{content.plant_id or 'all'}-{int(datetime.now(timezone.utc).timestamp())}.csv"
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([content.title])
        writer.writerow([f"Period: {content.date_range_start.isoformat()} to {content.date_range_end.isoformat()}"])
        writer.writerow([])
        writer.writerow(["Executive Summary"])
        writer.writerow([_sanitize_cell(content.executive_summary)])
        writer.writerow([])

        for section in content.sections:
            if section.kind != "table" or not section.table_headers:
                continue
            writer.writerow([section.heading])
            writer.writerow(section.table_headers)
            for row in section.table_rows or []:
                writer.writerow([_sanitize_cell(cell) for cell in row])
            writer.writerow([])

        writer.writerow(["Recommendations"])
        for rec in content.recommendations:
            writer.writerow([_sanitize_cell(rec)])

    return str(file_path)
