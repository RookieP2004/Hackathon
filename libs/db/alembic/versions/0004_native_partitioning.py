"""native partitioning for incidents, alerts, notifications

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-22

DATABASE_SCHEMA.md §9, §11, §17 / §22.1: these three tables are "business
objects with a lifecycle" (mutated repeatedly, not pure append-only), so they
use native PostgreSQL declarative RANGE partitioning by created_at (monthly),
NOT TimescaleDB hypertables — see §0.5's regime distinction.

Postgres cannot convert an existing regular table into a partitioned table via
ALTER TABLE — the only path is to create a new partitioned table with the same
structure and either swap or migrate data in. Since these tables were only just
created by migration 0003 and are still empty, DROP + recreate is safe and
correct here; a real production migration with live data would instead create
the partitioned table under a temporary name, copy data across, then rename.
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS incidents CASCADE")
    op.execute(
        """
        CREATE TABLE incidents (
            id                    BIGINT GENERATED ALWAYS AS IDENTITY,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            incident_number       TEXT NOT NULL,
            plant_id              BIGINT NOT NULL REFERENCES plants(id) ON DELETE RESTRICT,
            zone_id               BIGINT REFERENCES zones(id) ON DELETE SET NULL,
            equipment_id          BIGINT REFERENCES equipment(id) ON DELETE SET NULL,
            severity              TEXT NOT NULL,
            status                TEXT NOT NULL DEFAULT 'open',
            ai_generated_summary  TEXT,
            root_cause            TEXT,
            opened_by_user_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
            acknowledged_by       BIGINT REFERENCES users(id) ON DELETE SET NULL,
            closed_by             BIGINT REFERENCES users(id) ON DELETE SET NULL,
            opened_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
            acknowledged_at       TIMESTAMPTZ,
            escalated_at          TIMESTAMPTZ,
            closed_at             TIMESTAMPTZ,
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, created_at),
            -- Postgres requires every unique constraint on a partitioned table to
            -- include the partition key -- incident_number is generated to be globally
            -- unique regardless, so this composite constraint carries no practical
            -- weakening versus a plain UNIQUE(incident_number) on a non-partitioned table.
            CONSTRAINT uq_incidents_incident_number_created_at UNIQUE (incident_number, created_at)
        ) PARTITION BY RANGE (created_at)
        """
    )
    op.execute("CREATE INDEX idx_incidents_plant_id ON incidents(plant_id, created_at)")
    op.execute("CREATE INDEX idx_incidents_zone_id ON incidents(zone_id, created_at) WHERE zone_id IS NOT NULL")
    op.execute(
        "CREATE INDEX idx_incidents_equipment_id ON incidents(equipment_id, created_at) WHERE equipment_id IS NOT NULL"
    )
    op.execute("CREATE INDEX idx_incidents_open ON incidents(status, severity) WHERE status IN ('open','acknowledged','escalated')")
    op.execute("CREATE INDEX idx_incidents_summary_trgm ON incidents USING gin (ai_generated_summary gin_trgm_ops)")
    op.execute(
        "CREATE TRIGGER trg_incidents_updated_at BEFORE UPDATE ON incidents FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    op.execute("DROP TABLE IF EXISTS alerts CASCADE")
    op.execute(
        """
        CREATE TABLE alerts (
            id                 BIGINT GENERATED ALWAYS AS IDENTITY,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            alert_type         TEXT NOT NULL,
            severity           TEXT NOT NULL,
            status             TEXT NOT NULL DEFAULT 'open',
            equipment_id       BIGINT REFERENCES equipment(id) ON DELETE SET NULL,
            zone_id            BIGINT REFERENCES zones(id) ON DELETE SET NULL,
            sensor_id          BIGINT REFERENCES sensors(id) ON DELETE SET NULL,
            related_incident_id BIGINT,
            message            TEXT NOT NULL,
            triggered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            acknowledged_by    BIGINT REFERENCES users(id) ON DELETE SET NULL,
            acknowledged_at    TIMESTAMPTZ,
            resolved_at        TIMESTAMPTZ,
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
        """
    )
    op.execute("CREATE INDEX idx_alerts_equipment_id ON alerts(equipment_id, created_at) WHERE equipment_id IS NOT NULL")
    op.execute("CREATE INDEX idx_alerts_zone_id ON alerts(zone_id, created_at) WHERE zone_id IS NOT NULL")
    op.execute("CREATE INDEX idx_alerts_sensor_id ON alerts(sensor_id, created_at) WHERE sensor_id IS NOT NULL")
    op.execute("CREATE INDEX idx_alerts_open ON alerts(severity, triggered_at) WHERE status = 'open'")
    op.execute("CREATE INDEX idx_alerts_incident_id ON alerts(related_incident_id) WHERE related_incident_id IS NOT NULL")
    op.execute(
        "CREATE TRIGGER trg_alerts_notify AFTER INSERT ON alerts FOR EACH ROW EXECUTE FUNCTION notify_new_alert()"
    )

    op.execute("DROP TABLE IF EXISTS notifications CASCADE")
    op.execute(
        """
        CREATE TABLE notifications (
            id                   BIGINT GENERATED ALWAYS AS IDENTITY,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            user_id              BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            channel              notification_channel NOT NULL,
            severity             TEXT NOT NULL,
            related_incident_id  BIGINT,
            related_alert_id     BIGINT,
            message              TEXT NOT NULL,
            status               TEXT NOT NULL DEFAULT 'pending',
            sent_at              TIMESTAMPTZ,
            delivered_at         TIMESTAMPTZ,
            acknowledged_at      TIMESTAMPTZ,
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
        """
    )
    op.execute("CREATE INDEX idx_notifications_user_id ON notifications(user_id, created_at)")
    op.execute(
        "CREATE INDEX idx_notifications_pending ON notifications(status, severity) WHERE status IN ('pending','sent')"
    )
    op.execute(
        "CREATE INDEX idx_notifications_incident_id ON notifications(related_incident_id) WHERE related_incident_id IS NOT NULL"
    )

    # Initial partitions: current month plus 3 months ahead, matching DATABASE_SCHEMA.md
    # §22.5's pg_partman premake=3 policy. A scheduled job (not modeled in this migration)
    # must keep creating future partitions in production — see that section's explicit
    # warning about the self-inflicted-outage failure mode of forgetting to.
    op.execute(
        """
        DO $$
        DECLARE
            month_start date := date_trunc('month', now())::date;
            i integer;
            tbl text;
        BEGIN
            FOREACH tbl IN ARRAY ARRAY['incidents', 'alerts', 'notifications'] LOOP
                FOR i IN 0..3 LOOP
                    EXECUTE format(
                        'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                        tbl || '_' || to_char(month_start + (i || ' months')::interval, 'YYYY_MM'),
                        tbl,
                        month_start + (i || ' months')::interval,
                        month_start + ((i + 1) || ' months')::interval
                    );
                END LOOP;
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS incidents CASCADE")
