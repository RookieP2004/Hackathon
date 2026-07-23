from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_type: str
    generated_by: int | None
    plant_id: int | None
    date_range_start: date
    date_range_end: date
    parameters: dict
    status: str
    file_url: str | None
    schedule_cron: str | None
    generated_at: datetime | None
    created_at: datetime


class ReportCreate(BaseModel):
    report_type: str = Field(min_length=1, max_length=100)
    plant_id: int | None = None
    date_range_start: date
    date_range_end: date
    parameters: dict = Field(default_factory=dict)
    schedule_cron: str | None = None

    @model_validator(mode="after")
    def _date_range_must_be_valid(self) -> "ReportCreate":
        if self.date_range_end < self.date_range_start:
            raise ValueError("date_range_end must be on or after date_range_start")
        return self


class ReportCompleteRequest(BaseModel):
    file_url: str = Field(min_length=1)


class ReportFilter(BaseModel):
    report_type: str | None = None
    plant_id: int | None = None
    status: str | None = None
