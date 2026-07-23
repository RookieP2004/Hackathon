"""
Renders any ReportContent into a real, professionally laid-out PDF (fpdf2) --
one renderer for all eleven enterprise report types, since they all share the
same ReportContent shape (app/reports/content.py).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.pdf_text import sanitize_for_pdf
from app.reports.content import ReportContent

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "generated_reports" / "enterprise"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class _EnterpriseReportPDF(FPDF):
    def __init__(self, title: str) -> None:
        super().__init__()
        self._report_title = title

    def header(self) -> None:
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, sanitize_for_pdf(f"AEGIS AI -- {self._report_title}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
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

    def data_table(self, headers: list[str], rows: list[list]) -> None:
        self.set_font("Helvetica", "", 8)
        all_rows = [headers] + [[sanitize_for_pdf(str(cell)) for cell in row] for row in rows]
        with self.table(text_align="LEFT") as table:
            for row in all_rows:
                table.row(row)
        self.ln(2)


def render_pdf(content: ReportContent) -> str:
    pdf = _EnterpriseReportPDF(content.title)
    pdf.add_page()

    pdf.section_title(f"{content.title} ({content.date_range_start.isoformat()} to {content.date_range_end.isoformat()})")
    pdf.body_text(content.executive_summary)

    chart_paths_to_clean = []
    for section in content.sections:
        pdf.section_title(section.heading)
        if section.kind == "text":
            pdf.body_text(section.text or "")
        elif section.kind == "table":
            pdf.data_table(section.table_headers or [], section.table_rows or [])
        elif section.kind == "chart" and section.chart_path:
            pdf.image(section.chart_path, w=170)
            pdf.ln(2)
            chart_paths_to_clean.append(section.chart_path)

    pdf.section_title("Recommendations")
    for rec in content.recommendations:
        pdf.body_text(f"- {rec}")

    file_path = REPORTS_DIR / f"{content.report_type}-{content.plant_id or 'all'}-{int(datetime.now(timezone.utc).timestamp())}.pdf"
    pdf.output(str(file_path))

    for chart_path in chart_paths_to_clean:
        try:
            os.remove(chart_path)
        except OSError:
            pass

    return str(file_path)
