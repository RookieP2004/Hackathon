"""
Python mirrors of every Postgres ENUM type from DATABASE_SCHEMA.md §2.
Values must stay byte-for-byte identical to the Postgres CREATE TYPE ... AS ENUM
statements in alembic/versions/0002_enums.py — these are two representations of
the same contract, not independent sources of truth.
"""

from __future__ import annotations

import enum


class SeverityLevel(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ADVISORY = "advisory"


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    CLOSED = "closed"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"


class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    PUSH = "push"
    SMS = "sms"
    EMAIL = "email"
    VOICE_CALL = "voice_call"


class MaintenanceStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PermitStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    CLOSED = "closed"


class AutonomyTier(str, enum.Enum):
    TIER_0_INFORM = "tier_0_inform"
    TIER_1_RECOMMEND = "tier_1_recommend"
    TIER_2_EXECUTE_NOTIFY = "tier_2_execute_notify"
    TIER_3_EXECUTE_VETO = "tier_3_execute_veto"


class EmergencyEventStatus(str, enum.Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"


class ReadingQuality(str, enum.Enum):
    GOOD = "good"
    UNCERTAIN = "uncertain"
    BAD = "bad"


class WorkerType(str, enum.Enum):
    EMPLOYEE = "employee"
    CONTRACTOR = "contractor"
    VISITOR = "visitor"


class CameraKind(str, enum.Enum):
    RGB = "rgb"
    THERMAL = "thermal"
    PTZ = "ptz"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class EquipmentStatus(str, enum.Enum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    UNDER_MAINTENANCE = "under_maintenance"
    OFFLINE = "offline"
    DECOMMISSIONED = "decommissioned"


class EmergencyStepStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
