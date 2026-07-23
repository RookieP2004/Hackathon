"""
The Agent Bus — AGENT_ARCHITECTURE.md §0.3's shared communication substrate,
implemented over real Redis Pub/Sub (already a provisioned dependency in
every service's config -- `redis_url` -- since Turn 1, just never actually
used for anything until now). Genuine cross-process publish/subscribe: this
is the same mechanism a fully distributed deployment (one agent per service)
would use, not an in-process stand-in that would need rewriting later --
today's topology (all twelve agents hosted in one process, agentic-
orchestrator) is a deployment choice, not a shortcut baked into the bus
itself.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import redis.asyncio as aioredis
import structlog

from aegis_agents.envelope import AgentMessage, MessageType

logger = structlog.get_logger(__name__)

REQUEST_TIMEOUT_SECONDS = 5.0


class MessageBus:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._redis = aioredis.from_url(self._redis_url)
        await self._redis.ping()

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()

    async def publish(self, topic: str, message: AgentMessage) -> None:
        assert self._redis is not None, "MessageBus.connect() must be called before publish()"
        await self._redis.publish(topic, json.dumps(message.to_dict()))

    async def subscribe(self, *topics: str) -> AsyncIterator[AgentMessage]:
        """An async generator over every message published to any of
        `topics`, for as long as the caller keeps iterating -- the standard
        shape every agent's asynchronous subscription (§0.3) uses."""
        assert self._redis is not None, "MessageBus.connect() must be called before subscribe()"
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(*topics)
        try:
            async for raw in pubsub.listen():
                if raw["type"] != "message":
                    continue
                try:
                    yield AgentMessage.from_dict(json.loads(raw["data"]))
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    logger.warning("bus_message_decode_failed", error=str(exc))
        finally:
            await pubsub.unsubscribe(*topics)

    async def request(
        self, *, requester_agent_id: str, requester_version: str, target_topic: str,
        response_topic: str, payload: dict, timeout: float = REQUEST_TIMEOUT_SECONDS,
    ) -> AgentMessage | None:
        """§0.3's synchronous-style request/response pattern: publish an
        `agent.request` message with a fresh correlation_id, then wait
        (bounded by `timeout`) for the matching `agent.response`. Returns
        None on timeout -- callers (e.g. Emergency Agent -> Permit Agent)
        are expected to treat a None response per their own fail-open/closed
        policy, never assume success silently."""
        assert self._redis is not None, "MessageBus.connect() must be called before request()"
        request_msg = AgentMessage(
            agent_id=requester_agent_id, agent_version=requester_version,
            message_type=MessageType.REQUEST, payload=payload,
        )

        pubsub = self._redis.pubsub()
        await pubsub.subscribe(response_topic)
        try:
            await self.publish(target_topic, request_msg)
            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return None
                raw = await pubsub.get_message(ignore_subscribe_messages=True, timeout=remaining)
                if raw is None:
                    continue
                try:
                    message = AgentMessage.from_dict(json.loads(raw["data"]))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
                if message.correlation_id == request_msg.correlation_id:
                    return message
        finally:
            await pubsub.unsubscribe(response_topic)
