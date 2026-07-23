"""
A single shared connection acquisition point for the fusion pipeline's many
small per-query helpers (pipeline.py, evidence.py, simulator.py). Every one
of those helpers used to open and close its own `asyncpg.connect()` -- on
the hot path that runs every fusion-loop tick and backs every `/fusion/assess`
call, `assess_equipment()` alone opened 10-15 raw connections per invocation.

`pool` is optional (defaults to `None`) precisely so this stays a pure
resource-management change, not a functionality change: every existing
caller (including every test that calls these helpers directly with just a
DSN) keeps working exactly as before, falling back to a standalone
connection per call. Only the two real hot paths -- `FusionLoop`'s
background tick and the `/fusion/assess` endpoint -- are wired to the real
`asyncpg.Pool` created once at service startup (see app/main.py).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg


@asynccontextmanager
async def acquire(dsn: str, pool: asyncpg.Pool | None) -> AsyncIterator[asyncpg.Connection]:
    if pool is not None:
        async with pool.acquire() as conn:
            yield conn
        return
    conn = await asyncpg.connect(dsn)
    try:
        yield conn
    finally:
        await conn.close()
