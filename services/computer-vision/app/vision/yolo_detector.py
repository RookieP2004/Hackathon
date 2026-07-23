"""
Real object detection via ultralytics YOLOv8n — the literal "Use YOLO"
requirement. COCO (the pretrained model's training set) has no notion of a
hard hat or a gas leak, so only the classes that are genuinely present in COCO
are mapped here: `person` -> Worker. Every other requested class (Helmet,
Vest, Forklift, Fire, Smoke, Gas Leak, Fallen Worker, Running Worker, Crowd,
Machine Obstruction) is handled by `synthetic_detector.py` instead, which
derives them from the factory simulation's own ground truth rather than
guessing at a COCO class that doesn't exist. See ARCHITECTURE.md §18.4
[HACKATHON SCOPE] for the rationale.

This module is the only place a real neural network runs; everything
downstream (persistence gate, alerts, risk inputs) treats its output
identically to the synthetic path's `Detection` objects.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Final

import numpy as np
import structlog
from PIL import Image
from ultralytics import YOLO

from app.vision.schema import BoundingBox, Detection, DetectionClass

logger = structlog.get_logger(__name__)

_WEIGHTS_PATH: Final = Path(__file__).resolve().parent.parent.parent / "models" / "yolov8n.pt"

# The only COCO class this deployment maps to one of our 13 taxonomy classes.
_COCO_CLASS_MAP: Final[dict[str, DetectionClass]] = {
    "person": DetectionClass.WORKER,
}

_MIN_CONFIDENCE: Final = 0.25


class YoloDetector:
    """Thin, lazily-initialized wrapper around one loaded ultralytics model."""

    def __init__(self, weights_path: Path = _WEIGHTS_PATH) -> None:
        self._weights_path = weights_path
        self._model: YOLO | None = None

    def _get_model(self) -> YOLO:
        if self._model is None:
            logger.info("yolo_model_loading", weights=str(self._weights_path))
            self._model = YOLO(str(self._weights_path))
            logger.info("yolo_model_loaded", classes=len(self._model.names))
        return self._model

    def warm_up(self) -> None:
        """Forces model load (and, on first-ever run, weight download) at
        startup instead of on the first inbound request."""
        self._get_model()

    def detect(self, image_bytes: bytes, camera_id: str, zone_id: str | None = None) -> list[Detection]:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        frame = np.array(image)

        model = self._get_model()
        results = model.predict(frame, verbose=False, conf=_MIN_CONFIDENCE)
        result = results[0]

        detections: list[Detection] = []
        for box in result.boxes:
            coco_name = result.names[int(box.cls[0])]
            mapped_class = _COCO_CLASS_MAP.get(coco_name)
            if mapped_class is None:
                continue  # not one of our 13 target classes -- COCO detects plenty we don't care about

            x1, y1, x2, y2 = box.xyxyn[0].tolist()
            detections.append(
                Detection(
                    detection_class=mapped_class,
                    confidence=float(box.conf[0]),
                    bounding_box=BoundingBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1),
                    camera_id=camera_id,
                    zone_id=zone_id,
                    source="yolo_inference",
                    metadata={"coco_class": coco_name},
                )
            )
        return detections


yolo_detector = YoloDetector()
