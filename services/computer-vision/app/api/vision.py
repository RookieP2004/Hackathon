from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from app.auth import auth
from app.vision.yolo_detector import yolo_detector

router = APIRouter(prefix="/vision", tags=["vision"])

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team", "government_auditor", "viewer")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer", "operator")

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post(
    "/detect",
    summary="Run real YOLOv8 object detection on an uploaded camera frame",
    description=(
        "Genuine ultralytics YOLOv8n inference (not simulated). Only Worker "
        "is currently mapped from this model's COCO training classes -- see "
        "app/vision/yolo_detector.py for why the other 12 requested classes "
        "have no COCO equivalent and are instead served by the live "
        "simulated pipeline at GET /vision/live."
    ),
)
async def detect_image(
    file: UploadFile = File(...), camera_id: str = Query(...), zone_id: str | None = Query(None),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
):
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="file must be an image")
    image_bytes = await file.read()
    if len(image_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=422, detail="image exceeds 10MB limit")

    detections = yolo_detector.detect(image_bytes, camera_id=camera_id, zone_id=zone_id)
    return {"camera_id": camera_id, "zone_id": zone_id, "detections": [d.to_dict() for d in detections]}


@router.get("/live", summary="Currently-confirmed detections across the live simulated camera feed")
async def get_live_detections(request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    pipeline = request.app.state.vision_pipeline
    return {
        "connected": pipeline.connected,
        "ticks_processed": pipeline.ticks_processed,
        "detections": pipeline.live_detections(),
    }


@router.get("/events", summary="Recent confirmed vision events (each entry is a persistence-gate-passed episode)")
async def get_recent_events(request: Request, limit: int = Query(100, ge=1, le=500), _principal=Depends(auth.require_roles(*_READ_ROLES))):
    pipeline = request.app.state.vision_pipeline
    return {"events": pipeline.recent_events(limit=limit)}
