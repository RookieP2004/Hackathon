"""
The Agent Bus's standard message envelope — AGENT_ARCHITECTURE.md §0.3 — used
on every topic (`agent.assertion`, `agent.request`/`agent.response`,
`agent.escalation`, `agent.health`) by every agent in the fleet, and the
Confidence Score standard (§0.5) every agent's output is normalized against.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum


class MessageType(str, Enum):
    ASSERTION = "assertion"
    REQUEST = "request"
    RESPONSE = "response"
    ESCALATION = "escalation"
    HEALTH = "health"


class ConfidenceBand(str, Enum):
    HIGH = "high"      # > 0.85 -- eligible for Tier 2+ autonomous action
    MEDIUM = "medium"  # 0.5-0.85 -- Tier 1 (recommend) only
    LOW = "low"        # < 0.5 -- Tier 0 (inform) only, watch-list


def confidence_band(score: float | None) -> ConfidenceBand | None:
    """§0.5's three calibration bands. Confidence bands govern autonomy
    ceiling, never truthfulness framing -- a Low-confidence assertion is
    never hidden, only routed to a lower-urgency surface."""
    if score is None:
        return None
    if score > 0.85:
        return ConfidenceBand.HIGH
    if score >= 0.5:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


@dataclass
class AgentMessage:
    agent_id: str
    agent_version: str
    message_type: MessageType
    payload: dict
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    confidence: float | None = None
    evidence_refs: list[str] = field(default_factory=list)
    produced_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reasoning: str | None = None  # the "explain reasoning" text -- not in §0.3's original envelope table, but every assertion/escalation this fleet produces carries one, per the fleet-wide "explain every decision" requirement

    def to_dict(self) -> dict:
        d = asdict(self)
        d["message_type"] = self.message_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AgentMessage":
        d = dict(d)
        d["message_type"] = MessageType(d["message_type"])
        return cls(**d)
