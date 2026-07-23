"""
Short-term conversational memory for the Copilot -- a session remembers the
last equipment/hazard mentioned so a follow-up question ("why is that
increasing?") doesn't need to repeat the equipment tag. Redis-backed with a
short TTL: this is a scratch conversational cache, not a durable record --
the durable record of what the system concluded and why is each agent's own
decision log and the incident timeline, both untouched by this cache.
"""

from __future__ import annotations

import json

import redis.asyncio as aioredis

_SESSION_TTL_SECONDS = 900
_KEY_PREFIX = "copilot:session:"


async def get_session_context(redis_url: str, session_id: str) -> dict:
    client = aioredis.from_url(redis_url)
    try:
        raw = await client.get(f"{_KEY_PREFIX}{session_id}")
        return json.loads(raw) if raw else {}
    finally:
        await client.aclose()


async def set_session_context(redis_url: str, session_id: str, context: dict) -> None:
    client = aioredis.from_url(redis_url)
    try:
        await client.set(f"{_KEY_PREFIX}{session_id}", json.dumps(context), ex=_SESSION_TTL_SECONDS)
    finally:
        await client.aclose()
