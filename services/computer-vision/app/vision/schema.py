"""
The Vision Agent's detection taxonomy — AGENT_ARCHITECTURE.md §2 and
ARCHITECTURE.md §18.1's capability set, extended with the specific classes
this module targets (Forklift, Fallen/Running Worker, Crowd, Machine
Obstruction go beyond the original doc's six capabilities but follow the same
shape: an object-detection class feeding the same `vision.inference` event
contract).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DetectionClass(str, Enum):
    HELMET = "helmet"
    VEST = "vest"
    GLOVES = "gloves"
    MASK = "mask"
    WORKER = "worker"
    FORKLIFT = "forklift"
    FIRE = "fire"
    SMOKE = "smoke"
    GAS_LEAK = "gas_leak"
    FALLEN_WORKER = "fallen_worker"
    RUNNING_WORKER = "running_worker"
    CROWD = "crowd"
    MACHINE_OBSTRUCTION = "machine_obstruction"


class Capability(str, Enum):
    """ARCHITECTURE.md §18.1's capability groupings — parallel per-capability
    detectors, not one monolithic classifier."""

    PPE_COMPLIANCE = "ppe_compliance"
    SMOKE_FIRE = "smoke_fire"
    INTRUSION_OCCUPANCY = "intrusion_occupancy"
    LEAK_SPILL = "leak_spill"
    EQUIPMENT_VISUAL_STATE = "equipment_visual_state"
    PERSONNEL_SAFETY = "personnel_safety"  # fallen/running worker — beyond the original six
    VEHICLE_DETECTION = "vehicle_detection"


CAPABILITY_OF: dict[DetectionClass, Capability] = {
    DetectionClass.HELMET: Capability.PPE_COMPLIANCE,
    DetectionClass.VEST: Capability.PPE_COMPLIANCE,
    DetectionClass.GLOVES: Capability.PPE_COMPLIANCE,
    DetectionClass.MASK: Capability.PPE_COMPLIANCE,
    DetectionClass.WORKER: Capability.INTRUSION_OCCUPANCY,
    DetectionClass.CROWD: Capability.INTRUSION_OCCUPANCY,
    DetectionClass.FORKLIFT: Capability.VEHICLE_DETECTION,
    DetectionClass.FIRE: Capability.SMOKE_FIRE,
    DetectionClass.SMOKE: Capability.SMOKE_FIRE,
    DetectionClass.GAS_LEAK: Capability.LEAK_SPILL,
    DetectionClass.FALLEN_WORKER: Capability.PERSONNEL_SAFETY,
    DetectionClass.RUNNING_WORKER: Capability.PERSONNEL_SAFETY,
    DetectionClass.MACHINE_OBSTRUCTION: Capability.EQUIPMENT_VISUAL_STATE,
}

# PPE violations and intrusion-into-elevated-risk-zone bypass the normal
# correlation latency (AGENT_ARCHITECTURE.md §2's Escalation Policy) — these
# classes go straight to an alert once the persistence gate passes, instead
# of waiting to be batched into the next risk-correlation cycle.
FAST_PATH_CLASSES = {
    DetectionClass.FIRE,
    DetectionClass.SMOKE,
    DetectionClass.GAS_LEAK,
    DetectionClass.FALLEN_WORKER,
    DetectionClass.MACHINE_OBSTRUCTION,
    DetectionClass.HELMET,
    DetectionClass.VEST,
    DetectionClass.GLOVES,
    DetectionClass.MASK,
}


@dataclass(frozen=True)
class BoundingBox:
    """Normalized to the [0, 1] range within whatever frame produced it — resolution-independent, matching how the real /vision/detect endpoint's YOLO output is normalized before being returned."""

    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict:
        return {"x": round(self.x, 4), "y": round(self.y, 4), "width": round(self.width, 4), "height": round(self.height, 4)}


@dataclass(frozen=True)
class Detection:
    detection_class: DetectionClass
    confidence: float
    bounding_box: BoundingBox
    camera_id: str
    zone_id: str | None = None
    source: str = "simulated"  # "yolo_inference" | "simulated"
    object_id: str | None = None  # e.g. the worker_id/equipment_id this detection corresponds to, when known
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "detection_class": self.detection_class.value,
            "confidence": round(self.confidence, 4),
            "bounding_box": self.bounding_box.to_dict(),
            "camera_id": self.camera_id,
            "zone_id": self.zone_id,
            "source": self.source,
            "object_id": self.object_id,
            "metadata": self.metadata,
        }
