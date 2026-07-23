"""
Continuous background pipeline: the Vision Agent's "camera feed" is
iot-simulator's live WebSocket telemetry stream. There is no real camera in
this environment, so the factory simulation's own live state IS the ground
truth a real camera would eventually observe -- see synthetic_detector.py's
docstring for how each detection is derived from it honestly, not fabricated.

One tick = one inbound snapshot. Every detection observed that tick is run
through the persistence gate (persistence.py), keyed by (object/zone/camera
id, detection_class), so a single-frame flicker never reaches an event.
Only detections that just crossed the persistence threshold trigger a NEW
downstream call (alert and/or risk score) -- an already-confirmed, still-
ongoing detection stays visible in the live view without re-alerting every
tick. Plain Worker presence is excluded from downstream calls: occupancy by
itself isn't an anomaly (that's what Crowd is for).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
import websockets

from app.config import Settings
from app.vision.downstream import DownstreamIntegration
from app.vision.persistence import PersistenceGate
from app.vision.schema import FAST_PATH_CLASSES, Detection, DetectionClass
from app.vision.synthetic_detector import detect_from_snapshot

logger = structlog.get_logger(__name__)

MAX_EVENT_LOG = 500
RECONNECT_DELAY_SECONDS = 3


@dataclass
class VisionEvent:
    detection: Detection
    persistence_factor: float
    is_confirmed: bool
    just_crossed_threshold: bool
    observed_at: str

    def to_dict(self) -> dict:
        return {
            **self.detection.to_dict(),
            "persistence_factor": round(self.persistence_factor, 3),
            "is_confirmed": self.is_confirmed,
            "observed_at": self.observed_at,
        }


class VisionPipeline:
    def __init__(self, settings: Settings, downstream: DownstreamIntegration, required_consecutive: int = 3) -> None:
        self._settings = settings
        self._downstream = downstream
        self._gate = PersistenceGate(required_consecutive=required_consecutive)
        self._live: dict[tuple[str, str], VisionEvent] = {}
        self._tracked_keys: set[tuple[str, str]] = set()
        self._event_log: list[VisionEvent] = []
        self._connected = False
        self._task: asyncio.Task | None = None
        self._ticks_processed = 0

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def ticks_processed(self) -> int:
        return self._ticks_processed

    def live_detections(self) -> list[dict]:
        return [e.to_dict() for e in self._live.values()]

    def recent_events(self, limit: int = 100) -> list[dict]:
        return [e.to_dict() for e in self._event_log[-limit:]]

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
                async with websockets.connect(self._settings.iot_simulator_ws_url) as ws:
                    self._connected = True
                    logger.info("vision_pipeline_connected", url=self._settings.iot_simulator_ws_url)
                    async for raw in ws:
                        await self.process_tick(json.loads(raw))
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 -- any connection failure should retry, not crash the pipeline
                self._connected = False
                logger.warning("vision_pipeline_disconnected", error=str(exc))
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    async def process_tick(self, snapshot: dict) -> list[VisionEvent]:
        """Runs detection + the persistence gate for one snapshot and fires any
        downstream calls that just became due. Returns the events newly
        confirmed this tick (empty most ticks). Public + synchronous-friendly
        entry point so tests can drive it directly without a live WebSocket."""
        self._ticks_processed += 1
        detections = detect_from_snapshot(snapshot)
        now = datetime.now(timezone.utc).isoformat()
        seen_keys: set[tuple[str, str]] = set()
        newly_confirmed: list[VisionEvent] = []

        for detection in detections:
            key = (detection.object_id or detection.zone_id or detection.camera_id, detection.detection_class.value)
            seen_keys.add(key)
            result = self._gate.observe(key, detected=True)
            event = VisionEvent(detection, result.persistence_factor, result.is_confirmed, result.just_crossed_threshold, now)

            if result.is_confirmed:
                self._live[key] = event

            if result.just_crossed_threshold:
                self._event_log.append(event)
                if len(self._event_log) > MAX_EVENT_LOG:
                    self._event_log = self._event_log[-MAX_EVENT_LOG:]
                newly_confirmed.append(event)
                await self._dispatch_downstream(detection, result.persistence_factor)

        for key in self._tracked_keys - seen_keys:
            self._gate.observe(key, detected=False)
            self._live.pop(key, None)
        self._tracked_keys = seen_keys

        return newly_confirmed

    async def _dispatch_downstream(self, detection: Detection, persistence_factor: float) -> None:
        if detection.detection_class == DetectionClass.WORKER:
            return  # bare occupancy isn't an anomaly -- Crowd is the risk-worthy escalation of it
        if detection.detection_class in FAST_PATH_CLASSES:
            await self._downstream.raise_alert(detection, persistence_factor)
        await self._downstream.submit_risk_score(detection, persistence_factor)
