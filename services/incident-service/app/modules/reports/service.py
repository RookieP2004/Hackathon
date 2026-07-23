from __future__ import annotations

from datetime import datetime, timezone

from aegis_api_common import InvalidStateError, NotFoundError
from aegis_db.models import Report
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.schemas import ReportCreate


async def get_report_or_404(db: AsyncSession, report_id: int) -> Report:
    report = await db.get(Report, report_id)
    if report is None:
        raise NotFoundError(f"Report {report_id} not found")
    return report


async def create_report(db: AsyncSession, payload: ReportCreate, *, generated_by: int) -> Report:
    report = Report(
        report_type=payload.report_type,
        generated_by=generated_by,
        plant_id=payload.plant_id,
        date_range_start=payload.date_range_start,
        date_range_end=payload.date_range_end,
        parameters=payload.parameters,
        schedule_cron=payload.schedule_cron,
        status="pending",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def complete_report(db: AsyncSession, report_id: int, file_url: str) -> Report:
    report = await get_report_or_404(db, report_id)
    if report.status == "completed":
        raise InvalidStateError(f"Report {report_id} is already completed")
    report.status = "completed"
    report.file_url = file_url
    report.generated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(report)
    return report
