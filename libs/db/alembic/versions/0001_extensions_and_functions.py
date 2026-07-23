"""extensions and trigger functions

Revision ID: 0001
Revises:
Create Date: 2026-07-22 00:00:00
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DATABASE_SCHEMA.md §1
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # DATABASE_SCHEMA.md §1.1 — global trigger functions
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_row_change()
        RETURNS TRIGGER AS $$
        DECLARE
            v_actor_user_id BIGINT;
        BEGIN
            BEGIN
                v_actor_user_id := current_setting('app.current_user_id', true)::BIGINT;
            EXCEPTION WHEN OTHERS THEN
                v_actor_user_id := NULL;
            END;

            INSERT INTO audit_logs (actor_user_id, action, resource_type, resource_id, old_value, new_value, occurred_at)
            VALUES (
                v_actor_user_id,
                TG_OP,
                TG_TABLE_NAME,
                COALESCE(NEW.id, OLD.id),
                CASE WHEN TG_OP IN ('UPDATE','DELETE') THEN to_jsonb(OLD) ELSE NULL END,
                CASE WHEN TG_OP IN ('UPDATE','INSERT') THEN to_jsonb(NEW) ELSE NULL END,
                now()
            );
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION '% is an append-only table -- % is not permitted on table %', TG_TABLE_NAME, TG_OP, TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION notify_new_alert()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify('aegis_new_alert', json_build_object(
                'id', NEW.id, 'severity', NEW.severity, 'equipment_id', NEW.equipment_id, 'zone_id', NEW.zone_id
            )::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS notify_new_alert()")
    op.execute("DROP FUNCTION IF EXISTS prevent_mutation()")
    op.execute("DROP FUNCTION IF EXISTS audit_row_change()")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    # Extensions are intentionally not dropped on downgrade — other databases on
    # the same cluster / a concurrent migration may depend on them.
