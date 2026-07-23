"""
The Risk Fusion Engine's own independent background loop: ticks the sensor
simulator (writing real readings into `sensor_readings`) and periodically
re-assesses a small watch-list of real equipment, exactly the same
lifespan-managed background-task pattern iot-simulator and computer-vision's
`VisionPipeline` already use in this codebase.
"""

from __future__ import annotations

import asyncio

import asyncpg
import structlog

from aegis_api_common import ServiceActorTokenMinter

from app.fusion.pipeline import assess_equipment
from app.fusion.simulator import SensorSimulator

logger = structlog.get_logger(__name__)

# The Zone 3 / Reactor Feed Line cluster RISK_FUSION_ENGINE.md §5's worked
# example narrates -- reassessed every tick so the demo has genuinely live,
# continuously-updating risk scores to show, the same way iot-simulator
# continuously drives the factory map/dashboard.
DEFAULT_WATCH_LIST = [2, 3, 4]  # V-12, RV-9, R-3


class FusionLoop:
    def __init__(self, simulator: SensorSimulator, *, postgres_dsn: str, knowledge_graph_url: str,
                 computer_vision_url: str, tick_seconds: float, token_minter: ServiceActorTokenMinter,
                 watch_list: list[int] | None = None, pg_pool: asyncpg.Pool | None = None) -> None:
        self._simulator = simulator
        self._postgres_dsn = postgres_dsn
        self._knowledge_graph_url = knowledge_graph_url
        self._computer_vision_url = computer_vision_url
        self._tick_seconds = tick_seconds
        self._token_minter = token_minter
        self._watch_list = watch_list or DEFAULT_WATCH_LIST
        self._pg_pool = pg_pool
        self._task: asyncio.Task | None = None
        self._ticks = 0
        self._last_error: str | None = None

    @property
    def ticks(self) -> int:
        return self._ticks

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def start(self) -> None:
        self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_forever(self) -> None:
        while True:
            try:
                await self._simulator.tick_and_persist(self._postgres_dsn, self._pg_pool)
                for equipment_id in self._watch_list:
                    await assess_equipment(
                        equipment_id=equipment_id, postgres_dsn=self._postgres_dsn,
                        knowledge_graph_url=self._knowledge_graph_url, computer_vision_url=self._computer_vision_url,
                        token_minter=self._token_minter, pg_pool=self._pg_pool,
                    )
                self._ticks += 1
                self._last_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 -- a bad tick should never kill the loop
                self._last_error = str(exc)
                logger.warning("fusion_loop_tick_failed", error=str(exc))
            await asyncio.sleep(self._tick_seconds)
