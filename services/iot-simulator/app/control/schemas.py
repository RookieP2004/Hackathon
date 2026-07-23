from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.scenarios import SCENARIO_TYPES

ModeName = Literal["normal", "warning", "critical"]
ScenarioName = Literal["gas_leak", "explosion", "machine_failure", "worker_collapse", "fire"]


class ModeRequest(BaseModel):
    mode: ModeName
    zone_id: str | None = Field(default=None, description="Omit to set the global default mode for every zone.")


class ScenarioRequest(BaseModel):
    scenario: ScenarioName
    zone_id: str | None = Field(default=None, description="Required unless equipment_id or worker_id is given.")
    equipment_id: str | None = None
    worker_id: str | None = None

    @model_validator(mode="after")
    def _requires_a_target(self) -> "ScenarioRequest":
        if self.zone_id is None and self.equipment_id is None and self.worker_id is None:
            raise ValueError("One of zone_id, equipment_id, or worker_id is required")
        if self.scenario == "machine_failure" and self.equipment_id is None:
            raise ValueError("machine_failure requires equipment_id")
        if self.scenario == "worker_collapse" and self.worker_id is None:
            raise ValueError("worker_collapse requires worker_id")
        return self


class ResetRequest(BaseModel):
    zone_id: str | None = Field(default=None, description="Omit to reset the entire factory to Normal mode.")


class ScenarioTypesResponse(BaseModel):
    scenario_types: list[str] = list(SCENARIO_TYPES)
