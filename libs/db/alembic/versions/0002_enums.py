"""enum types

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-22 00:01:00
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# DATABASE_SCHEMA.md §2 — must stay byte-for-byte identical to aegis_db/enums.py
ENUMS: dict[str, list[str]] = {
    "severity_level": ["critical", "high", "medium", "low", "advisory"],
    "incident_status": ["open", "acknowledged", "escalated", "closed"],
    "alert_status": ["open", "acknowledged", "resolved", "suppressed"],
    "notification_status": ["pending", "sent", "delivered", "failed", "acknowledged"],
    "notification_channel": ["in_app", "push", "sms", "email", "voice_call"],
    "maintenance_status": ["scheduled", "in_progress", "completed", "cancelled"],
    "permit_status": ["draft", "active", "expired", "revoked", "closed"],
    "autonomy_tier": [
        "tier_0_inform",
        "tier_1_recommend",
        "tier_2_execute_notify",
        "tier_3_execute_veto",
    ],
    "emergency_event_status": ["initiated", "in_progress", "completed", "aborted"],
    "reading_quality": ["good", "uncertain", "bad"],
    "worker_type": ["employee", "contractor", "visitor"],
    "camera_kind": ["rgb", "thermal", "ptz"],
    "report_status": ["pending", "generating", "ready", "failed"],
    "equipment_status": ["operational", "degraded", "under_maintenance", "offline", "decommissioned"],
}


def upgrade() -> None:
    for type_name, values in ENUMS.items():
        values_sql = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {type_name} AS ENUM ({values_sql})")


def downgrade() -> None:
    for type_name in reversed(list(ENUMS.keys())):
        op.execute(f"DROP TYPE IF EXISTS {type_name}")
