from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, apply_filters, apply_sorting, get_logger, paginate, parse_sort
from aegis_db.models import Report
from app.auth import auth
from app.db import get_db
from app.modules.reports import service
from app.modules.reports.schemas import ReportCompleteRequest, ReportCreate, ReportFilter, ReportRead

router = APIRouter(prefix="/reports", tags=["reports"])
logger = get_logger("incident-service.reports")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "government_auditor")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer")

_SORTABLE_FIELDS = {"id", "report_type", "status", "created_at"}


@router.get("", response_model=Page[ReportRead], summary="List reports")
async def list_reports(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: ReportFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[ReportRead]:
    query = apply_filters(select(Report), Report, filters)
    query = apply_sorting(query, Report, sort_fields, _SORTABLE_FIELDS, default_field="id")
    return await paginate(db, query, pagination, ReportRead)


@router.get(
    "/{report_id}",
    response_model=ReportRead,
    summary="Get a report by ID",
    responses={404: {"description": "Report not found"}},
)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> ReportRead:
    report = await service.get_report_or_404(db, report_id)
    return ReportRead.model_validate(report)


@router.post(
    "",
    response_model=ReportRead,
    status_code=201,
    summary="Request a report",
    description="Creates a report request in 'pending' status; generation happens out-of-band and is recorded via the /complete action.",
)
async def create_report(
    payload: ReportCreate,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> ReportRead:
    report = await service.create_report(db, payload, generated_by=principal.user_id)
    logger.info("report_requested", report_id=report.id, report_type=report.report_type)
    return ReportRead.model_validate(report)


@router.post(
    "/{report_id}/complete",
    response_model=ReportRead,
    summary="Mark a report as generated",
    responses={404: {"description": "Report not found"}, 422: {"description": "Report is already completed"}},
)
async def complete_report(
    report_id: int,
    payload: ReportCompleteRequest,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> ReportRead:
    report = await service.complete_report(db, report_id, payload.file_url)
    logger.info("report_completed", report_id=report.id)
    return ReportRead.model_validate(report)
