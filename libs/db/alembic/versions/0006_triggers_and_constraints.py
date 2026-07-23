"""triggers: updated_at, audit logging, immutability; shift EXCLUDE constraint

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-22

Wires up the trigger functions defined in migration 0001 to the actual tables
that need them, plus the shift-overlap EXCLUDE constraint from
DATABASE_SCHEMA.md §6.4 that cannot be expressed via SQLAlchemy Table args.
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# Every table using TimestampMixin (aegis_db/base.py) needs the DB-level
# set_updated_at trigger — the Python-side onupdate is a client-side
# convenience only, per that mixin's own docstring.
TIMESTAMP_MIXIN_TABLES = [
    "plants", "buildings", "zones", "equipment", "machines", "sensors",
    "users", "workers", "shifts", "permits", "maintenance_records",
    "playbooks", "emergency_events", "cameras",
]

# DATABASE_SCHEMA.md's explicit per-table audit-trigger list — access-control
# and safety-relevant tables where every change is a compliance-relevant event
# (§21.5, §15's "every approval/rejection is a safety-critical, auditable decision").
AUDITED_TABLES = [
    "users", "permits", "user_role_scopes", "playbooks",
    "emergency_events", "emergency_event_steps",
]

# Append-only tables — mutation is a hard error, not merely discouraged.
IMMUTABLE_TABLES = ["audit_logs", "incident_timeline_events"]


def upgrade() -> None:
    for table in TIMESTAMP_MIXIN_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )

    for table in AUDITED_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_audit AFTER INSERT OR UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION audit_row_change()"
        )

    for table in IMMUTABLE_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_prevent_{table}_mutation BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION prevent_mutation()"
        )

    # DATABASE_SCHEMA.md §6.4 — a worker cannot be double-booked into overlapping
    # shifts, enforced at the database level via GiST exclusion (requires
    # btree_gist, enabled in migration 0001).
    op.execute(
        "ALTER TABLE shift_assignments ADD CONSTRAINT excl_shift_assignments_worker_period "
        "EXCLUDE USING gist (worker_id WITH =, period WITH &&)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE shift_assignments DROP CONSTRAINT IF EXISTS excl_shift_assignments_worker_period")
    for table in IMMUTABLE_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_prevent_{table}_mutation ON {table}")
    for table in AUDITED_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_audit ON {table}")
    for table in TIMESTAMP_MIXIN_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
