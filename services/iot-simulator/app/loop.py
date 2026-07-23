"""The per-second heartbeat: tick the simulation, broadcast the snapshot."""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.domain.engine import SimulationEngine
from app.ws.manager import ConnectionManager

logger = get_logger("iot-simulator.loop")


async def run_tick_loop(engine: SimulationEngine, manager: ConnectionManager, interval_seconds: float) -> None:
    while True:
        try:
            snapshot = engine.tick()
            await manager.broadcast(snapshot)
        except Exception:
            logger.error("tick_loop_error", exc_info=True)
        await asyncio.sleep(interval_seconds)
