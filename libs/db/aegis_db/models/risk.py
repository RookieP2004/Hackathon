"""
Risk Scores & Predictions — DATABASE_SCHEMA.md §10, §12. Owned by: predictive-risk-engine.

Both are TimescaleDB hypertables (converted via raw SQL in their Alembic
migrations, per DATABASE_SCHEMA.md §22.1) — composite PKs (id, time-column) are
required because the partitioning column must be part of every unique
constraint, declared via primary_key=True on both columns directly.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="CASCADE"))
    zone_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    predicted_window_start: Mapped[datetime | None] = mapped_column()
    predicted_window_end: Mapped[datetime | None] = mapped_column()
    contributing_factors: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        CheckConstraint(
            "equipment_id IS NOT NULL OR zone_id IS NOT NULL", name="chk_risk_target"
        ),
        Index("idx_risk_scores_equipment_id", "equipment_id", "computed_at"),
        Index("idx_risk_scores_zone_id", "zone_id", "computed_at"),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    target_metric: Mapped[str] = mapped_column(String, nullable=False)
    predicted_value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    prediction_horizon_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_outcome: Mapped[float | None] = mapped_column(Numeric(14, 4))
    outcome_recorded_at: Mapped[datetime | None] = mapped_column()
    predicted_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        Index("idx_predictions_equipment_id", "equipment_id", "predicted_at"),
        Index("idx_predictions_model", "model_name", "model_version", "predicted_at"),
    )
