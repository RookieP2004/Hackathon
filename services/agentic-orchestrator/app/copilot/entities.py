"""
Entity extraction for the Copilot -- resolves equipment and hazard-class
mentions in free text against the real seeded vocabulary (equipment
tags/names from Postgres, the five real hazard classes the Risk Fusion
Engine actually reasons over), rather than guessing or hallucinating an
entity that doesn't exist.
"""

from __future__ import annotations

import asyncpg

from aegis_agents.db import acquire

_HAZARD_SYNONYMS: dict[str, str] = {
    "gas leak": "gas_leak", "gas_leak": "gas_leak", "toxic release": "gas_leak", "toxic": "gas_leak",
    "h2s": "gas_leak", "leak": "gas_leak",
    "worker injury": "worker_injury", "worker_injury": "worker_injury", "injury": "worker_injury", "exposure": "worker_injury",
    "machine failure": "machine_failure", "machine_failure": "machine_failure", "breakdown": "machine_failure", "failure": "machine_failure",
    "explosion": "explosion", "explode": "explosion", "blast": "explosion",
    "fire": "fire", "burn": "fire", "flame": "fire",
}


def resolve_hazard_class(text: str) -> str | None:
    lowered = text.lower()
    # Longest phrase first: "gas leak" must win over a bare "leak" substring match.
    for phrase in sorted(_HAZARD_SYNONYMS, key=len, reverse=True):
        if phrase in lowered:
            return _HAZARD_SYNONYMS[phrase]
    return None


async def resolve_equipment(postgres_dsn: str, text: str, pool: asyncpg.Pool | None = None) -> dict | None:
    async with acquire(postgres_dsn, pool) as conn:
        rows = await conn.fetch("SELECT id, tag, name, zone_id FROM equipment")

    lowered = text.lower()
    candidates = [row for row in rows if row["tag"].lower() in lowered or row["name"].lower() in lowered]
    if not candidates:
        return None
    best = max(candidates, key=lambda row: max(len(row["tag"]), len(row["name"])))
    return {"equipment_id": best["id"], "tag": best["tag"], "name": best["name"], "zone_id": best["zone_id"]}
