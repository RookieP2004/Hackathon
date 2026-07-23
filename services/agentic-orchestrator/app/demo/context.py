"""
The shared handle every Demo Mode action receives -- real service clients and
a scratch `state` dict actions use to pass real ids (a permit id created in
one step that a later step needs to expire, the bus a later step listens on
for the real automatic emergency response) to each other across the script.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import asyncpg
from aegis_agents import MessageBus

from app.orchestrator.clients import ServiceClients


@dataclass
class DemoContext:
    clients: ServiceClients
    postgres_dsn: str
    bus: MessageBus
    iot_simulator_url: str
    state: dict = field(default_factory=dict)
    pg_pool: asyncpg.Pool | None = None
