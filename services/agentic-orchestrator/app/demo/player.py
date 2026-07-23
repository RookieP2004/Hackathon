"""
The Demo Mode playback controller -- runs the real scripted story
(app/demo/script.py) as a background asyncio task, with real pause/resume/
stop/fast-forward. Actions themselves are atomic real operations and are
never interrupted mid-call; pause/fast-forward only affect the pacing
between steps.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import structlog

from aegis_agents import MessageBus
from app.demo.context import DemoContext
from app.demo.script import build_script
from app.orchestrator.clients import ServiceClients

logger = structlog.get_logger(__name__)

_SLEEP_GRANULARITY_SECONDS = 0.5


class DemoPlayer:
    def __init__(self, *, clients: ServiceClients, postgres_dsn: str, bus: MessageBus, iot_simulator_url: str) -> None:
        self._clients = clients
        self._postgres_dsn = postgres_dsn
        self._bus = bus
        self._iot_simulator_url = iot_simulator_url

        self._task: asyncio.Task | None = None
        self._status = "idle"  # idle | running | paused | completed | failed | stopped
        self._speed_multiplier = 1.0
        self._current_step_index = -1
        self._step_log: list[dict] = []
        self._started_at: float | None = None

        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # set == not paused

    def start(self, *, speed_multiplier: float = 1.0) -> dict:
        if self._status in ("running", "paused"):
            return {"started": False, "reason": f"a demo run is already {self._status}"}

        self._speed_multiplier = max(0.1, speed_multiplier)
        self._current_step_index = -1
        self._step_log = []
        self._started_at = time.monotonic()
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._status = "running"

        ctx = DemoContext(clients=self._clients, postgres_dsn=self._postgres_dsn, bus=self._bus, iot_simulator_url=self._iot_simulator_url)
        self._task = asyncio.create_task(self._run(ctx))
        return {"started": True}

    def pause(self) -> dict:
        if self._status != "running":
            return {"paused": False, "reason": f"demo is not running (status={self._status})"}
        self._pause_event.clear()
        self._status = "paused"
        return {"paused": True}

    def resume(self) -> dict:
        if self._status != "paused":
            return {"resumed": False, "reason": f"demo is not paused (status={self._status})"}
        self._pause_event.set()
        self._status = "running"
        return {"resumed": True}

    def stop(self) -> dict:
        if self._status not in ("running", "paused"):
            return {"stopped": False, "reason": f"demo is not active (status={self._status})"}
        self._stop_event.set()
        self._pause_event.set()  # unblock a paused sleep so it can observe the stop
        self._status = "stopped"
        return {"stopped": True}

    def set_speed(self, speed_multiplier: float) -> dict:
        self._speed_multiplier = max(0.1, speed_multiplier)
        return {"speed_multiplier": self._speed_multiplier}

    def replay(self) -> dict:
        self.stop()
        return self.start(speed_multiplier=self._speed_multiplier)

    def status(self) -> dict:
        script = build_script()
        elapsed = (time.monotonic() - self._started_at) if self._started_at is not None else 0.0
        current_step = script[self._current_step_index] if 0 <= self._current_step_index < len(script) else None
        return {
            "status": self._status,
            "speed_multiplier": self._speed_multiplier,
            "elapsed_seconds": round(elapsed, 1),
            "current_step_index": self._current_step_index,
            "current_step_id": current_step.id if current_step else None,
            "total_steps": len(script),
            "timeline": [{"id": s.id, "title": s.title, "narration": s.narration} for s in script],
            "step_log": self._step_log,
        }

    async def _run(self, ctx: DemoContext) -> None:
        script = build_script()
        for index, step in enumerate(script):
            if self._stop_event.is_set():
                return
            await self._pause_event.wait()
            if self._stop_event.is_set():
                return

            self._current_step_index = index
            entry = {"id": step.id, "title": step.title, "narration": step.narration, "started_at": datetime.now(timezone.utc).isoformat()}
            try:
                result = await step.action(ctx)
                entry["result"] = result
                entry["ok"] = True
            except Exception as exc:
                logger.warning("demo_step_failed", step_id=step.id, error=str(exc))
                entry["result"] = {"error": str(exc)}
                entry["ok"] = False
            entry["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._step_log.append(entry)

            await self._interruptible_sleep(step.wait_after_seconds)
            if self._stop_event.is_set():
                return

        self._status = "completed"

    async def _interruptible_sleep(self, seconds: float) -> None:
        remaining = seconds / self._speed_multiplier
        while remaining > 0 and not self._stop_event.is_set():
            await self._pause_event.wait()
            if self._stop_event.is_set():
                return
            chunk = min(_SLEEP_GRANULARITY_SECONDS, remaining)
            await asyncio.sleep(chunk)
            remaining -= chunk
