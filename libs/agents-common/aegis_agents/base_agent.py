"""
BaseAgent — the shared shell every one of the fleet's twelve agents runs
inside, implementing AGENT_ARCHITECTURE.md §0's meta-architecture once
rather than reimplementing it per agent: runs independently as its own
asyncio task, communicates over the real Agent Bus (bus.py), maintains
working/episodic memory (memory.py), emits a normalized confidence score on
every finding, logs every decision with its reasoning, and recovers from its
own tick failures according to its declared fail-open/fail-closed policy
(§0.6) rather than crashing the fleet or silently going dark.

Concrete agents subclass this and implement exactly one method, `tick()` --
one reasoning cycle of that agent's actual Core logic. Everything else
(the loop, the heartbeat, the retry/backoff, the bus wiring) is inherited.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Literal

import structlog

from aegis_agents.bus import MessageBus
from aegis_agents.envelope import AgentMessage, MessageType, confidence_band
from aegis_agents.memory import AgentMemory

logger = structlog.get_logger(__name__)

FailureMode = Literal["fail_open", "fail_closed"]


class BaseAgent(ABC):
    agent_id: str
    agent_version: str = "v1"
    failure_mode: FailureMode = "fail_open"
    tick_interval_seconds: float = 10.0
    max_consecutive_failures_before_degraded: int = 3

    def __init__(self, bus: MessageBus, postgres_dsn: str) -> None:
        self.bus = bus
        self.postgres_dsn = postgres_dsn
        self.memory = AgentMemory(postgres_dsn, self.agent_id, self.agent_version)
        self.working_memory: dict = {}
        self._task: asyncio.Task | None = None
        self._subscriber_task: asyncio.Task | None = None
        self._ticks = 0
        self._consecutive_failures = 0
        self._healthy = True
        self._last_error: str | None = None
        self._degraded_reason: str | None = None

    # ---- lifecycle ----

    def start(self) -> None:
        self._task = asyncio.create_task(self._run_forever(), name=self.agent_id)
        if self._has_subscriber_loop():
            self._subscriber_task = asyncio.create_task(self.run_subscriber_loop(), name=f"{self.agent_id}-subscriber")

    async def stop(self) -> None:
        for task in (self._task, self._subscriber_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def run_subscriber_loop(self) -> None:
        """Override for an agent whose Core is primarily a continuous Agent
        Bus listener (Permit Agent, Knowledge Agent -- §0.3's two
        "synchronous request/response" agents) rather than a periodic poll.
        No-op by default; `tick()` still runs alongside it for heartbeats
        and any secondary periodic bookkeeping the agent also needs."""
        return

    def _has_subscriber_loop(self) -> bool:
        return type(self).run_subscriber_loop is not BaseAgent.run_subscriber_loop

    async def _run_forever(self) -> None:
        while True:
            try:
                await self.tick()
                self._consecutive_failures = 0
                self._healthy = True
                self._last_error = None
                self._degraded_reason = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 -- a Core failure must never kill the agent's own loop
                await self._handle_tick_failure(exc)
            self._ticks += 1
            await self._publish_heartbeat()
            await asyncio.sleep(self.tick_interval_seconds)

    @abstractmethod
    async def tick(self) -> None:
        """One reasoning cycle of this agent's Core logic. Raise on genuine
        failure -- the base class's retry/degradation/fail-open-or-closed
        handling only activates when this actually raises, never silently."""

    # ---- failure handling (§0.6) ----

    async def _handle_tick_failure(self, exc: Exception) -> None:
        self._consecutive_failures += 1
        self._healthy = False
        self._last_error = str(exc)
        logger.warning("agent_tick_failed", agent_id=self.agent_id, error=str(exc), consecutive_failures=self._consecutive_failures)

        if self._consecutive_failures >= self.max_consecutive_failures_before_degraded:
            self._degraded_reason = f"{self._consecutive_failures} consecutive tick failures: {exc}"
            await self.on_degraded(exc)

    async def on_degraded(self, exc: Exception) -> None:
        """§0.6: fail-closed agents escalate their own unavailability as a
        blocking condition; fail-open agents log the degradation loudly
        (never a silent gap) but let the rest of the fleet continue."""
        if self.failure_mode == "fail_closed":
            await self.escalate(
                reason=f"{self.agent_id} is degraded and this agent fails closed -- treat as unable to verify",
                confidence=1.0, evidence_refs=[], payload={"error": str(exc), "consecutive_failures": self._consecutive_failures},
            )
        else:
            logger.warning("agent_degraded_fail_open", agent_id=self.agent_id, error=str(exc))

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    @property
    def degraded_reason(self) -> str | None:
        return self._degraded_reason

    # ---- Agent Bus helpers ----

    async def _publish_heartbeat(self) -> None:
        message = AgentMessage(
            agent_id=self.agent_id, agent_version=self.agent_version, message_type=MessageType.HEALTH,
            payload={
                "healthy": self._healthy, "ticks": self._ticks, "last_error": self._last_error,
                "degraded_reason": self._degraded_reason, "failure_mode": self.failure_mode,
            },
        )
        await self.bus.publish("agent.health", message)

    async def assert_finding(
        self, *, decision: str, reasoning: str, confidence: float, evidence_refs: list[str],
        payload: dict, correlation_id: str | None = None,
    ) -> AgentMessage:
        """Publishes an `agent.assertion`, logs the decision with its
        reasoning, and records the episode -- the three "maintain memory /
        log decisions / explain reasoning" requirements satisfied by every
        single finding any agent produces, in one call."""
        message = AgentMessage(
            agent_id=self.agent_id, agent_version=self.agent_version, message_type=MessageType.ASSERTION,
            confidence=confidence, evidence_refs=evidence_refs, payload=payload,
            correlation_id=correlation_id or self._new_correlation_id(), reasoning=reasoning,
        )
        await self.bus.publish("agent.assertion", message)
        await self.memory.log_decision(
            decision=decision, reasoning=reasoning, confidence=confidence,
            evidence_refs=evidence_refs, correlation_id=message.correlation_id,
        )
        await self.memory.remember_episode(kind="assertion", payload={"decision": decision, **payload})
        return message

    async def escalate(
        self, *, reason: str, confidence: float, evidence_refs: list[str], payload: dict,
        correlation_id: str | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            agent_id=self.agent_id, agent_version=self.agent_version, message_type=MessageType.ESCALATION,
            confidence=confidence, evidence_refs=evidence_refs, payload={"reason": reason, **payload},
            correlation_id=correlation_id or self._new_correlation_id(), reasoning=reason,
        )
        await self.bus.publish("agent.escalation", message)
        await self.memory.log_decision(decision="escalate", reasoning=reason, confidence=confidence, evidence_refs=evidence_refs, correlation_id=message.correlation_id)
        return message

    async def request(self, *, target_topic: str, response_topic: str, payload: dict, timeout: float = 5.0) -> AgentMessage | None:
        return await self.bus.request(
            requester_agent_id=self.agent_id, requester_version=self.agent_version,
            target_topic=target_topic, response_topic=response_topic, payload=payload, timeout=timeout,
        )

    async def respond(self, *, to: AgentMessage, payload: dict, confidence: float | None = None, evidence_refs: list[str] | None = None) -> None:
        message = AgentMessage(
            agent_id=self.agent_id, agent_version=self.agent_version, message_type=MessageType.RESPONSE,
            confidence=confidence, evidence_refs=evidence_refs or [], payload=payload, correlation_id=to.correlation_id,
        )
        await self.bus.publish(f"{to.agent_id}.response", message)

    @staticmethod
    def _new_correlation_id() -> str:
        import uuid

        return str(uuid.uuid4())

    @staticmethod
    def band_for(score: float) -> str | None:
        band = confidence_band(score)
        return band.value if band else None
