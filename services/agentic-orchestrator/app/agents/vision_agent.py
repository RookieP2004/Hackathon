"""
Vision Agent — AGENT_ARCHITECTURE.md §2. The Core (per-capability CV models
+ mandatory temporal-persistence gate) is already real and running in the
computer-vision service (built in the Vision AI pass, whose own docstrings
already cite this exact section). This agent doesn't reimplement that Core
-- it *is* the fleet-facing shell around it: polls computer-vision's real
confirmed-events feed and republishes each one onto the standard Agent Bus
envelope, which computer-vision's own bespoke REST API doesn't speak.
"""

from __future__ import annotations

import asyncpg
import httpx

from aegis_agents import BaseAgent
from aegis_api_common import ServiceActorTokenMinter
from app.agents import topics

FAST_PATH_CLASSES = {"fire", "smoke", "gas_leak", "fallen_worker", "machine_obstruction", "helmet", "vest", "gloves", "mask"}


class VisionAgent(BaseAgent):
    agent_id = "vision-agent"
    failure_mode = "fail_open"  # "but loudly" -- see the escalation on repeated fetch failure below
    tick_interval_seconds = 6.0

    def __init__(
        self, bus, postgres_dsn: str, computer_vision_url: str, *,
        jwt_secret: str, jwt_algorithm: str, pg_pool: asyncpg.Pool | None = None,
    ) -> None:
        super().__init__(bus, postgres_dsn, pg_pool)
        self._computer_vision_url = computer_vision_url
        self._last_seen_observed_at: str | None = None
        self._token_minter = ServiceActorTokenMinter(postgres_dsn=postgres_dsn, jwt_secret=jwt_secret, jwt_algorithm=jwt_algorithm)

    async def tick(self) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{self._computer_vision_url}/vision/events", params={"limit": 50}, headers=await self._token_minter.auth_headers(),
            )
            response.raise_for_status()
            events = response.json()["events"]

        new_events = [e for e in events if self._last_seen_observed_at is None or e["observed_at"] > self._last_seen_observed_at]
        if not new_events:
            return

        for event in new_events:
            fast_path = event["detection_class"] in FAST_PATH_CLASSES
            zone_suffix = f" (zone {event['zone_id']})" if event.get("zone_id") else ""
            fast_path_note = " Bypasses standard correlation latency (fast-path class)." if fast_path else ""
            reasoning = (
                f"computer-vision confirmed a '{event['detection_class']}' detection at {event['camera_id']}{zone_suffix}, "
                f"persistence-gated confidence {event['confidence'] * event['persistence_factor']:.2f}.{fast_path_note}"
            )
            await self.assert_finding(
                decision="vision_detection_confirmed",
                reasoning=reasoning,
                confidence=event["confidence"] * event["persistence_factor"],
                evidence_refs=[f"camera:{event['camera_id']}"] + ([f"object:{event['object_id']}"] if event.get("object_id") else []),
                payload={
                    "detection_class": event["detection_class"], "camera_id": event["camera_id"],
                    "zone_id": event.get("zone_id"), "fast_path": fast_path, "source": event.get("source"),
                },
            )

        self._last_seen_observed_at = max(e["observed_at"] for e in new_events)
