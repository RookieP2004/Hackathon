"""
Enterprise Reports -- one endpoint that generates any of the eleven report
types (Daily/Weekly/Monthly/Incident/RCA/Compliance/Safety Score/Machine
Health/Worker Safety/Permit/Maintenance) in PDF, Excel, or CSV, backed
entirely by real aggregated data (app/reports/data.py).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import auth
from app.orchestrator.clients import ServiceClients
from app.reports import data
from app.reports.render_csv import render_csv
from app.reports.render_excel import render_excel
from app.reports.render_pdf import render_pdf

router = APIRouter(prefix="/reports", tags=["reports"])

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team", "government_auditor", "viewer")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer")

_PERIOD_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}
_PLANT_SCOPED_TYPES = {"daily", "weekly", "monthly", "compliance", "safety_score", "machine_health", "worker_safety", "permit", "maintenance"}
_INCIDENT_SCOPED_TYPES = {"incident", "rca"}
_ALL_REPORT_TYPES = _PLANT_SCOPED_TYPES | _INCIDENT_SCOPED_TYPES

_RENDERERS = {"pdf": render_pdf, "excel": render_excel, "csv": render_csv}


class ReportGenerateRequest(BaseModel):
    report_type: str = Field(description=f"One of: {', '.join(sorted(_ALL_REPORT_TYPES))}")
    format: str = Field(default="pdf", pattern="^(pdf|excel|csv)$")
    plant_id: int | None = None
    date_range_start: date | None = None
    date_range_end: date | None = None
    incident_id: int | None = None


@router.post("/generate", summary="Generate one of the eleven enterprise report types, real data, any export format")
async def post_generate_report(payload: ReportGenerateRequest, request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    if payload.report_type not in _ALL_REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"Unknown report_type '{payload.report_type}'. Must be one of: {', '.join(sorted(_ALL_REPORT_TYPES))}")
    if payload.report_type in _PLANT_SCOPED_TYPES and payload.plant_id is None:
        raise HTTPException(status_code=422, detail=f"plant_id is required for report_type '{payload.report_type}'")
    if payload.report_type in _INCIDENT_SCOPED_TYPES and payload.incident_id is None:
        raise HTTPException(status_code=422, detail=f"incident_id is required for report_type '{payload.report_type}'")

    settings = request.app.state.settings
    clients: ServiceClients = request.app.state.copilot_clients
    postgres_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    if payload.report_type in _PERIOD_DAYS:
        end = payload.date_range_end or datetime.now(timezone.utc).date()
        start = payload.date_range_start or (end - timedelta(days=_PERIOD_DAYS[payload.report_type]))
        content = await data.aggregate_period_summary(postgres_dsn, plant_id=payload.plant_id, start=start, end=end, period_label=payload.report_type.capitalize())
    elif payload.report_type in _INCIDENT_SCOPED_TYPES:
        try:
            content = await data.aggregate_rca(clients, postgres_dsn, payload.incident_id, report_type=payload.report_type)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    elif payload.report_type == "compliance":
        content = await data.aggregate_compliance(clients, postgres_dsn, payload.plant_id)
    elif payload.report_type == "safety_score":
        end = payload.date_range_end or datetime.now(timezone.utc).date()
        start = payload.date_range_start or (end - timedelta(days=30))
        content = await data.compute_safety_score(postgres_dsn, plant_id=payload.plant_id, start=start, end=end)
    elif payload.report_type == "machine_health":
        content = await data.aggregate_machine_health(postgres_dsn, payload.plant_id)
    elif payload.report_type == "worker_safety":
        content = await data.aggregate_worker_safety(clients, postgres_dsn, payload.plant_id)
    elif payload.report_type == "permit":
        end = payload.date_range_end or datetime.now(timezone.utc).date()
        start = payload.date_range_start or (end - timedelta(days=30))
        content = await data.aggregate_permit_report(postgres_dsn, plant_id=payload.plant_id, start=start, end=end)
    else:  # maintenance
        end = payload.date_range_end or datetime.now(timezone.utc).date()
        start = payload.date_range_start or (end - timedelta(days=30))
        content = await data.aggregate_maintenance_report(postgres_dsn, plant_id=payload.plant_id, start=start, end=end)

    file_path = _RENDERERS[payload.format](content)

    report_row = await clients.create_report(
        report_type=content.report_type, plant_id=content.plant_id,
        parameters={"format": payload.format, "incident_id": payload.incident_id},
        date_range_start=content.date_range_start, date_range_end=content.date_range_end,
    )
    await clients.complete_report(report_row["id"], file_url=file_path)

    return {
        "report_id": report_row["id"], "report_type": content.report_type, "format": payload.format,
        "file_path": file_path, "title": content.title, "executive_summary": content.executive_summary,
        "recommendations": content.recommendations,
    }


@router.get("", summary="List generated enterprise reports")
async def get_reports(request: Request, plant_id: int | None = None, report_type: str | None = None, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    clients: ServiceClients = request.app.state.copilot_clients

    params = {"page_size": 50, "sort": "-created_at"}
    if plant_id is not None:
        params["plant_id"] = plant_id
    if report_type is not None:
        params["report_type"] = report_type
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{clients.incident_service_url}/reports", headers=await clients.auth_headers(), params=params)
        response.raise_for_status()
        return response.json()
