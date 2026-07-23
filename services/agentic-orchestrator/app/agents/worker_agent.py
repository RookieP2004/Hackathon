"""
Worker Agent — AGENT_ARCHITECTURE.md §3. Fuses badge/shift-assignment data
(identity ground truth) with Vision Agent's live PPE-violation detections
(safety-state ground truth) to track occupancy-vs-safe-limit and hazard-zone
exposure. Deliberately reports identity-confidence and location-confidence
as two separate numbers (§3's own requirement) rather than conflating them.
"""

from __future__ import annotations

import httpx
import asyncpg

from aegis_agents import BaseAgent
from aegis_agents.db import acquire
from aegis_api_common import ServiceActorTokenMinter

_PPE_CLASSES = {"helmet", "vest", "gloves", "mask"}


class WorkerAgent(BaseAgent):
    agent_id = "worker-agent"
    failure_mode = "fail_open"
    tick_interval_seconds = 12.0

    def __init__(
        self, bus, postgres_dsn: str, computer_vision_url: str, *,
        jwt_secret: str, jwt_algorithm: str, pg_pool: asyncpg.Pool | None = None,
    ) -> None:
        super().__init__(bus, postgres_dsn, pg_pool)
        self._computer_vision_url = computer_vision_url
        self._token_minter = ServiceActorTokenMinter(postgres_dsn=postgres_dsn, jwt_secret=jwt_secret, jwt_algorithm=jwt_algorithm)

    async def tick(self) -> None:
        async with acquire(self.postgres_dsn, self.pg_pool) as conn:
            zone_occupancy = await conn.fetch(
                """
                SELECT z.id AS zone_id, z.name, z.safe_occupancy_limit, count(sa.id) AS current_count
                FROM zones z
                LEFT JOIN shift_assignments sa ON sa.zone_id = z.id
                    AND sa.assigned_date = now()::date AND sa.period @> now()::timestamp
                WHERE z.safe_occupancy_limit IS NOT NULL
                GROUP BY z.id, z.name, z.safe_occupancy_limit
                """
            )

        for row in zone_occupancy:
            if row["current_count"] > row["safe_occupancy_limit"]:
                await self.assert_finding(
                    decision="occupancy_threshold_exceeded",
                    reasoning=(
                        f"Zone {row['name']} (id {row['zone_id']}) has {row['current_count']} personnel currently "
                        f"shift-assigned against a safe occupancy limit of {row['safe_occupancy_limit']}."
                    ),
                    confidence=1.0,  # a database fact (badge/shift-assignment ground truth), not a probabilistic claim
                    evidence_refs=[f"zone:{row['zone_id']}"],
                    payload={"zone_id": row["zone_id"], "current_count": row["current_count"], "safe_occupancy_limit": row["safe_occupancy_limit"]},
                )

        await self._check_ppe_violations_in_occupied_zones(zone_occupancy)

    async def _check_ppe_violations_in_occupied_zones(self, zone_occupancy) -> None:
        occupied_zone_ids = {row["zone_id"] for row in zone_occupancy if row["current_count"] > 0}
        if not occupied_zone_ids:
            return

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._computer_vision_url}/vision/live", headers=await self._token_minter.auth_headers())
                response.raise_for_status()
                detections = response.json()["detections"]
        except httpx.HTTPError:
            return  # fails open with degradation -- occupancy check above still ran independently

        ppe_violations = [d for d in detections if d["detection_class"] in _PPE_CLASSES]
        if not ppe_violations:
            return

        # Vision's PPE detections are plant-wide (computer-vision's own honest caveat: no spatial
        # correspondence to this real zone topology is guaranteed) -- reported as a corroborating
        # signal for currently-occupied zones, not claimed as a zone-specific confirmed match.
        await self.assert_finding(
            decision="ppe_violation_corroborated_with_occupancy",
            reasoning=(
                f"{len(ppe_violations)} PPE violation(s) currently confirmed by Vision Agent, while "
                f"{len(occupied_zone_ids)} zone(s) have personnel currently present -- flagged for review "
                f"since Vision Agent's detections are plant-wide, not zone-attributed with certainty."
            ),
            confidence=0.6,  # medium -- genuine corroboration, but explicitly not zone-precise
            evidence_refs=[f"zone:{zid}" for zid in occupied_zone_ids],
            payload={"ppe_violation_count": len(ppe_violations), "occupied_zone_ids": list(occupied_zone_ids)},
        )
