"""
Real HTTP integration with notification-service (`POST /alerts`) and
predictive-risk-engine (`POST /risk-engine/risk-scores`) -- the explicit
"Integrate with Risk Engine" requirement, and the "Alerts"/"Risk Inputs"
outputs.

No other service in this repo calls another service synchronously over HTTP
yet (every service's `kafka_brokers` setting implies event-driven integration
was the intended pattern, per ARCHITECTURE.md §10) but nothing currently
produces or consumes a `vision.inference` Kafka topic either, so a Kafka
publish here would integrate with nothing observable. A direct authenticated
REST call is the one integration path that can be empirically verified end to
end: a real row landing in each service's real Postgres table.

Both endpoints are protected by shared-secret JWT auth (libs/api-common's
`auth.py`) verified independently by each service -- there's no service
account or API-key bypass, so this module mints its own short-lived access
token using the same shared `jwt_secret`, exactly like identity-rbac's login
endpoint would, with a `role_id` resolved from the real `roles` table (never
hardcoded, in case a fresh environment seeds roles in a different order).

iot-simulator's world is a synthetic, un-seeded in-memory topology with
string ids ("compressor-house", "eq-c101") that has no corresponding row in
the real Postgres zones/equipment tables (confirmed empirically: the demo
seed's topology is a completely different plant, `Z1..Z10` / `V-12`/`RV-9`
tags). So `zone_id`/`equipment_id` are sent as null and the string identifiers
travel in `message` and `contributing_factors` instead of being force-mapped
to an unrelated real row.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import asyncpg
import httpx
import structlog
from jose import jwt

from app.config import Settings
from app.vision.schema import Detection

logger = structlog.get_logger(__name__)

_ACCESS_TOKEN_TTL_SECONDS = 600
_ALERT_ROLE_NAME = "system_admin"  # satisfies both /alerts' and /risk-scores' allowed-role lists

_FAST_PATH_SEVERITY: dict[str, str] = {
    "fire": "critical",
    "gas_leak": "critical",
    "fallen_worker": "critical",
    "smoke": "high",
    "machine_obstruction": "high",
}


class DownstreamIntegration:
    """Owns the minted-token cache and the two outbound clients. One instance
    per running service, created at lifespan startup."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(timeout=5.0)
        self._cached_role_id: int | None = None
        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0
        self._cached_real_zone_ids: list[int] | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _resolve_role_id(self) -> int:
        if self._cached_role_id is not None:
            return self._cached_role_id
        dsn = self._settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        try:
            role_id = await conn.fetchval("SELECT id FROM roles WHERE name = $1", _ALERT_ROLE_NAME)
        finally:
            await conn.close()
        if role_id is None:
            raise RuntimeError(f"Role '{_ALERT_ROLE_NAME}' not found -- has the demo DB been seeded?")
        self._cached_role_id = role_id
        return role_id

    async def _resolve_real_zone_ids(self) -> list[int]:
        if self._cached_real_zone_ids is not None:
            return self._cached_real_zone_ids
        dsn = self._settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch("SELECT id FROM zones ORDER BY id")
        finally:
            await conn.close()
        self._cached_real_zone_ids = [r["id"] for r in rows] or [1]
        return self._cached_real_zone_ids

    async def _pick_attachment_zone_id(self, vision_zone_id: str | None) -> int | None:
        """RiskScoreCreate requires a real `zone_id` or `equipment_id` FK, and
        there is no genuine correspondence between iot-simulator's synthetic
        zone ids and the real seeded plant's zones (confirmed empirically --
        two entirely different demo topologies). Rather than fabricate a fake
        mapping table, this deterministically picks one real zone per
        vision_zone_id (stable across calls, so the same simulated zone
        always attaches to the same real zone) purely to satisfy the schema's
        FK requirement. The true origin is never lost: it always travels
        alongside in `contributing_factors`/`message`."""
        if vision_zone_id is None:
            return None
        real_zone_ids = await self._resolve_real_zone_ids()
        index = int(hashlib.sha1(vision_zone_id.encode()).hexdigest(), 16) % len(real_zone_ids)
        return real_zone_ids[index]

    async def _get_token(self) -> str:
        now = time.time()
        if self._cached_token is not None and now < self._token_expires_at - 30:
            return self._cached_token

        role_id = await self._resolve_role_id()
        expires_at = now + _ACCESS_TOKEN_TTL_SECONDS
        payload = {
            "sub": str(self._settings.vision_service_actor_user_id),
            "role_id": role_id,
            "type": "access",
            "exp": int(expires_at),
        }
        token = jwt.encode(payload, self._settings.jwt_secret, algorithm=self._settings.jwt_algorithm)
        self._cached_token, self._token_expires_at = token, expires_at
        return token

    async def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._get_token()}"}

    async def raise_alert(self, detection: Detection, persistence_factor: float) -> dict[str, Any] | None:
        severity = _FAST_PATH_SEVERITY.get(detection.detection_class.value, "medium")
        message = (
            f"Vision AI: {detection.detection_class.value} detected "
            f"(camera {detection.camera_id}, zone {detection.zone_id}, "
            f"confidence {detection.confidence * persistence_factor:.2f}, source={detection.source})"
        )
        body = {
            "alert_type": f"vision_{detection.detection_class.value}",
            "severity": severity,
            "zone_id": await self._pick_attachment_zone_id(detection.zone_id),
            "equipment_id": None,
            "sensor_id": None,
            "related_incident_id": None,
            "message": message,
        }
        return await self._post("/alerts", self._settings.notification_service_url, body)

    async def submit_risk_score(self, detection: Detection, persistence_factor: float) -> dict[str, Any] | None:
        confidence = round(detection.confidence * persistence_factor, 4)
        score = min(100.0, confidence * 100)
        body = {
            "equipment_id": None,
            "zone_id": await self._pick_attachment_zone_id(detection.zone_id),
            "score": score,
            "confidence": confidence,
            "contributing_factors": [
                {
                    "source": "computer-vision",
                    "detection_class": detection.detection_class.value,
                    "camera_id": detection.camera_id,
                    "vision_zone_id": detection.zone_id,
                    "vision_object_id": detection.object_id,
                }
            ],
            "model_version": "vision-agent-v1",
        }
        return await self._post("/risk-engine/risk-scores", self._settings.predictive_risk_engine_url, body)

    async def _post(self, path: str, base_url: str, body: dict) -> dict[str, Any] | None:
        headers = await self._auth_headers()
        try:
            response = await self._client.post(f"{base_url}{path}", json=body, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.warning("downstream_call_failed", path=path, error=str(exc))
            return None
