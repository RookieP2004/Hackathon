from __future__ import annotations

from datetime import datetime, timezone

from aegis_api_common import InvalidStateError, NotFoundError
from aegis_db.models import Alert
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.alerts.schemas import AlertCreate


async def get_alert_or_404(db: AsyncSession, alert_id: int) -> Alert:
    # Alert's PK is composite (id, created_at) — the table is native-partitioned
    # by created_at (same pattern as Incident; see aegis_db.models.incidents'
    # module docstring). `id` alone is still globally unique (one shared sequence).
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise NotFoundError(f"Alert {alert_id} not found")
    return alert


async def create_alert(db: AsyncSession, payload: AlertCreate) -> Alert:
    alert = Alert(
        alert_type=payload.alert_type,
        severity=payload.severity,
        status="open",
        equipment_id=payload.equipment_id,
        zone_id=payload.zone_id,
        sensor_id=payload.sensor_id,
        related_incident_id=payload.related_incident_id,
        message=payload.message,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


async def acknowledge_alert(db: AsyncSession, alert_id: int, *, actor_user_id: int) -> Alert:
    alert = await get_alert_or_404(db, alert_id)
    if alert.status != "open":
        raise InvalidStateError(f"Alert {alert_id} must be 'open' to acknowledge (currently '{alert.status}')")
    alert.status = "acknowledged"
    alert.acknowledged_by = actor_user_id
    alert.acknowledged_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(alert)
    return alert


async def resolve_alert(db: AsyncSession, alert_id: int) -> Alert:
    alert = await get_alert_or_404(db, alert_id)
    if alert.status == "resolved":
        raise InvalidStateError(f"Alert {alert_id} is already resolved")
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(alert)
    return alert
