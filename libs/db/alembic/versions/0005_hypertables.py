"""timescaledb hypertable conversion + compression + retention policies

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-22

DATABASE_SCHEMA.md §10, §12, §14, §15, §16, §19, §20, §21, §22 — every genuinely
high-frequency, append-only table becomes a TimescaleDB hypertable. sensor_readings
gets the additional space dimension (sensor_id) per §20's 2D-partitioning
rationale; every other hypertable here is time-only.

worker_location_history is NOT part of the original DATABASE_SCHEMA.md design
(see aegis_db/models/timeseries.py's docstring for why it was added and the
privacy-by-design constraints it carries) — its retention (90 days) is
deliberately short and finite, matching that stated intent.
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# (table, time_column, chunk_interval, retention_interval_or_None, compress_after, segmentby)
HYPERTABLES = [
    ("risk_scores", "computed_at", "1 day", "180 days", "14 days", "equipment_id"),
    ("predictions", "predicted_at", "1 day", "180 days", "14 days", "equipment_id"),
    ("camera_events", "detected_at", "1 day", "30 days", "3 days", "camera_id"),
    ("ppe_violations", "detected_at", "1 day", "30 days", "3 days", "zone_id"),
    ("audit_logs", "occurred_at", "1 month", None, "90 days", "resource_type"),
    ("weather_observations", "observed_at", "1 day", "1 year", "30 days", "plant_id"),
    ("machine_state_history", "recorded_at", "1 day", None, "7 days", "machine_id"),
    ("worker_location_history", "recorded_at", "1 day", "90 days", "7 days", "worker_id"),
]


def upgrade() -> None:
    for table, time_col, chunk_interval, _retention, _compress_after, _segmentby in HYPERTABLES:
        op.execute(
            f"SELECT create_hypertable('{table}', '{time_col}', chunk_time_interval => INTERVAL '{chunk_interval}')"
        )

    # sensor_readings: the one 2D-partitioned hypertable in the schema (time + sensor_id),
    # per DATABASE_SCHEMA.md §20's explicit rationale — the highest-volume table, where
    # per-sensor query concentration justifies the added chunking complexity.
    #
    # TimescaleDB requires every unique index (including the PK) to include all
    # partitioning dimensions -- confirmed empirically: add_dimension() below
    # rejected the original (id, recorded_at) PK. The PK is widened to include
    # sensor_id before adding it as a second dimension.
    op.execute("ALTER TABLE sensor_readings DROP CONSTRAINT pk_sensor_readings")
    op.execute("ALTER TABLE sensor_readings ADD CONSTRAINT pk_sensor_readings PRIMARY KEY (id, recorded_at, sensor_id)")
    op.execute("SELECT create_hypertable('sensor_readings', 'recorded_at', chunk_time_interval => INTERVAL '1 day')")
    op.execute("SELECT add_dimension('sensor_readings', 'sensor_id', number_partitions => 8)")

    # Compression policies (§22.2) — segmentby chosen per table to match its
    # dominant query filter, so compression works with the access pattern.
    op.execute("ALTER TABLE risk_scores SET (timescaledb.compress, timescaledb.compress_segmentby = 'equipment_id')")
    op.execute("SELECT add_compression_policy('risk_scores', INTERVAL '14 days')")

    op.execute("ALTER TABLE predictions SET (timescaledb.compress, timescaledb.compress_segmentby = 'equipment_id')")
    op.execute("SELECT add_compression_policy('predictions', INTERVAL '14 days')")

    op.execute("ALTER TABLE camera_events SET (timescaledb.compress, timescaledb.compress_segmentby = 'camera_id')")
    op.execute("SELECT add_compression_policy('camera_events', INTERVAL '3 days')")

    op.execute("ALTER TABLE ppe_violations SET (timescaledb.compress, timescaledb.compress_segmentby = 'zone_id')")
    op.execute("SELECT add_compression_policy('ppe_violations', INTERVAL '3 days')")

    op.execute("ALTER TABLE audit_logs SET (timescaledb.compress, timescaledb.compress_segmentby = 'resource_type')")
    op.execute("SELECT add_compression_policy('audit_logs', INTERVAL '90 days')")

    op.execute(
        "ALTER TABLE weather_observations SET (timescaledb.compress, timescaledb.compress_segmentby = 'plant_id')"
    )
    op.execute("SELECT add_compression_policy('weather_observations', INTERVAL '30 days')")

    op.execute(
        "ALTER TABLE sensor_readings SET (timescaledb.compress, timescaledb.compress_segmentby = 'sensor_id', timescaledb.compress_orderby = 'recorded_at DESC')"
    )
    op.execute("SELECT add_compression_policy('sensor_readings', INTERVAL '7 days')")

    op.execute(
        "ALTER TABLE machine_state_history SET (timescaledb.compress, timescaledb.compress_segmentby = 'machine_id')"
    )
    op.execute("SELECT add_compression_policy('machine_state_history', INTERVAL '7 days')")

    op.execute(
        "ALTER TABLE worker_location_history SET (timescaledb.compress, timescaledb.compress_segmentby = 'worker_id')"
    )
    op.execute("SELECT add_compression_policy('worker_location_history', INTERVAL '7 days')")

    # Retention policies (§22.3) — audit_logs deliberately has NONE, per NFR-17:
    # compressed after 90 days, never dropped.
    op.execute("SELECT add_retention_policy('risk_scores', INTERVAL '180 days')")
    op.execute("SELECT add_retention_policy('predictions', INTERVAL '180 days')")
    op.execute("SELECT add_retention_policy('camera_events', INTERVAL '30 days')")
    op.execute("SELECT add_retention_policy('ppe_violations', INTERVAL '30 days')")
    op.execute("SELECT add_retention_policy('weather_observations', INTERVAL '1 year')")
    op.execute("SELECT add_retention_policy('sensor_readings', INTERVAL '90 days')")
    op.execute("SELECT add_retention_policy('worker_location_history', INTERVAL '90 days')")
    # machine_state_history: no retention policy — cumulative_operating_hours/cycle_count
    # history has ongoing value for predictive-maintenance trend analysis (RISK_FUSION_ENGINE.md
    # §4.5); compressed at 7 days but not dropped, a deliberate choice distinct from
    # sensor_readings' 90-day drop (which relies on continuous aggregates instead, DATABASE_SCHEMA.md §22.4).

    # Continuous aggregates (§22.4) — 1-minute and 1-hour rollups for sensor_readings,
    # so 90-day raw retention can coexist with long-range trend views.
    #
    # `CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)` cannot run inside
    # a transaction block (confirmed empirically: "cannot run inside a transaction
    # block") — this whole migration otherwise runs inside one enclosing transaction
    # (per alembic/env.py's context.begin_transaction() wrapping the full upgrade
    # batch), so these two statements specifically must escape it via
    # autocommit_block(), Alembic's documented mechanism for exactly this class of
    # Postgres/Timescale DDL.
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE MATERIALIZED VIEW sensor_readings_1min
            WITH (timescaledb.continuous) AS
            SELECT sensor_id,
                   time_bucket('1 minute', recorded_at) AS bucket,
                   avg(value) AS avg_value,
                   min(value) AS min_value,
                   max(value) AS max_value,
                   count(*) FILTER (WHERE quality <> 'good') AS bad_reading_count
            FROM sensor_readings
            GROUP BY sensor_id, bucket
            """
        )
        op.execute(
            "SELECT add_continuous_aggregate_policy('sensor_readings_1min', start_offset => INTERVAL '3 days', end_offset => INTERVAL '1 minute', schedule_interval => INTERVAL '1 minute')"
        )

    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE MATERIALIZED VIEW sensor_readings_1hour
            WITH (timescaledb.continuous) AS
            SELECT sensor_id,
                   time_bucket('1 hour', recorded_at) AS bucket,
                   avg(value) AS avg_value, min(value) AS min_value, max(value) AS max_value
            FROM sensor_readings
            GROUP BY sensor_id, bucket
            """
        )
        op.execute(
            "SELECT add_continuous_aggregate_policy('sensor_readings_1hour', start_offset => INTERVAL '30 days', end_offset => INTERVAL '1 hour', schedule_interval => INTERVAL '1 hour')"
        )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS sensor_readings_1hour")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS sensor_readings_1min")
    # Hypertable conversion is not reversed here — downgrading a hypertable back to a
    # plain table is a rare, manual operation in real Timescale usage and is out of
    # scope for an automatic downgrade path.
