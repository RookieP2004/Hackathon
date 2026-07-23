"""Weather — DATABASE_SCHEMA.md §19. Owned by: ingestion-gateway. TimescaleDB hypertable."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False)
    temperature_c: Mapped[float | None] = mapped_column(Numeric(5, 2))
    humidity_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    wind_speed_ms: Mapped[float | None] = mapped_column(Numeric(6, 2))
    wind_direction_deg: Mapped[int | None] = mapped_column(SmallInteger)
    precipitation_mm: Mapped[float | None] = mapped_column(Numeric(6, 2))
    conditions: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False)

    __table_args__ = (
        CheckConstraint("wind_direction_deg BETWEEN 0 AND 359", name="wind_direction_range"),
        Index("idx_weather_plant_id", "plant_id", "observed_at"),
    )
