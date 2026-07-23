"""
A single shared connection-acquisition point, mirroring predictive-risk-engine's
app/fusion/db.py -- every agent, `AgentMemory`, and `ServiceClients` used to open
and close its own `asyncpg.connect()` per call, on a fleet that runs continuously
for the entire life of a demo. `pool` is optional (default `None`) precisely so
this stays a pure resource-management change: every existing caller keeps working
unchanged, falling back to a standalone connection per call.
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
