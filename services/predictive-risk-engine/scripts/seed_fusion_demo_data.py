"""
Seeds two small, real, idempotent facts into the already-seeded demo DB so
the Risk Fusion Engine's V-12/RV-9/R-3 cluster (Zone 3, Reactor Feed Line --
the same equipment RISK_FUSION_ENGINE.md §5's worked example narrates) can
reproduce that trace's Category B context for real: an overdue relief-valve
inspection on RV-9, and one worker currently shift-assigned to Zone 3.
Neither fact exists in the original demo seed (libs/db/seed) -- both are
additive, idempotent (safe to re-run), and clearly scoped to this specific
demo narrative rather than altering the base seed.

Usage: python scripts/seed_fusion_demo_data.py
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

import asyncpg

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"

RV9_EQUIPMENT_ID = 3
ZONE_3_ID = 3
WORKER_ID = 3  # Dr. Elena Kwan, per the demo seed's roster


async def seed() -> None:
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        existing = await conn.fetchval(
            "SELECT id FROM maintenance_records WHERE equipment_id = $1 AND description = $2",
            RV9_EQUIPMENT_ID, "Relief valve inspection (RISK_FUSION_ENGINE.md worked-example demo fact)",
        )
        if existing is None:
            await conn.execute(
                """
                INSERT INTO maintenance_records (equipment_id, maintenance_type_id, status, scheduled_date, description)
                VALUES ($1, 4, 'scheduled', $2, $3)
                """,
                RV9_EQUIPMENT_ID, date.today() - timedelta(days=45),
                "Relief valve inspection (RISK_FUSION_ENGINE.md worked-example demo fact)",
            )
            print("Seeded overdue RV-9 maintenance record (45 days overdue)")
        else:
            print("RV-9 overdue maintenance record already exists, skipping")

        existing_shift = await conn.fetchval(
            "SELECT id FROM shifts WHERE plant_id = 1 AND name = 'Demo Day Shift'"
        )
        if existing_shift is None:
            existing_shift = await conn.fetchval(
                "INSERT INTO shifts (plant_id, name, start_time, end_time) VALUES (1, 'Demo Day Shift', '06:00', '18:00') RETURNING id"
            )
            print("Seeded Demo Day Shift")

        existing_assignment = await conn.fetchval(
            "SELECT id FROM shift_assignments WHERE worker_id = $1 AND zone_id = $2 AND assigned_date = $3",
            WORKER_ID, ZONE_3_ID, date.today(),
        )
        if existing_assignment is None:
            await conn.execute(
                """
                INSERT INTO shift_assignments (shift_id, worker_id, zone_id, assigned_date, period)
                VALUES ($1, $2, $3, $4, tsrange((now() - interval '2 hours')::timestamp, (now() + interval '6 hours')::timestamp))
                """,
                existing_shift, WORKER_ID, ZONE_3_ID, date.today(),
            )
            print(f"Seeded shift assignment: worker {WORKER_ID} -> zone {ZONE_3_ID}, today")
        else:
            print("Shift assignment already exists, skipping")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
