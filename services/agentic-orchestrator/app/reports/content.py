"""
The common shape every enterprise report is assembled into before rendering.
One aggregator per report type (app/reports/data.py) builds a ReportContent
out of real data; one renderer per export format (render_pdf.py,
render_excel.py, render_csv.py) consumes that same shape -- so adding a
report type never means writing three bespoke renderers, and a renderer
never needs to know which of the eleven report types it's drawing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ReportSection:
    heading: str
    kind: str  # "text" | "table" | "chart"
    text: str | None = None
    table_headers: list[str] | None = None
    table_rows: list[list] | None = None
    chart_path: str | None = None


@dataclass
class ReportContent:
    report_type: str
    title: str
    plant_id: int | None
    date_range_start: date
    date_range_end: date
    executive_summary: str
    sections: list[ReportSection] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
