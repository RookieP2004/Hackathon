"""Reports — DATABASE_SCHEMA.md §18. Owned by: incident-service."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String, nullable=False)
    generated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    plant_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("plants.id", ondelete="SET NULL"))
    date_range_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_range_end: Mapped[date] = mapped_column(Date, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    file_url: Mapped[str | None] = mapped_column(String)
    schedule_cron: Mapped[str | None] = mapped_column(String)
    generated_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("date_range_end >= date_range_start", name="chk_report_date_range"),
        Index("idx_reports_plant_id", "plant_id"),
        Index("idx_reports_generated_by", "generated_by"),
    )
