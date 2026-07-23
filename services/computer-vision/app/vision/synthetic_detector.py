"""
The "honest synthetic" detection path — ARCHITECTURE.md §18.4 [HACKATHON SCOPE]
sanctions exactly this shortfall: most of the 13 requested classes (PPE items,
Forklift, Fire, Smoke, Gas Leak, Fallen/Running Worker, Crowd, Machine
Obstruction) have no COCO equivalent a pretrained YOLO model could ever
recognize, and no labeled industrial-safety training set exists in this
environment to fine-tune one.

Rather than fabricating arbitrary numbers, every function below re-expresses
ground truth the factory simulation (iot-simulator) already computed --
`worker.status`, `zone.camera.event_type`, `equipment.status`, the vehicle
list, worker vitals -- in detection-shaped form (bounding box, confidence,
camera_id), so the rest of the pipeline (persistence gate, alerts, risk
inputs) cannot tell it apart from a genuine vision detection. Running Worker
in particular is inferred from elevated heart rate rather than GPS-delta
motion: worker GPS in the simulator is pure positional jitter (noise, not
directed movement), so treating it as a speed signal would itself be a
fabrication, whereas an elevated heart rate is a real physiological signal the
simulation already drives toward "warning" during scenario onset, and is a
defensible proxy for physical exertion consistent with running.
"""

from __future__ import annotations

import hashlib

from app.vision.schema import BoundingBox, Detection, DetectionClass

GAS_LEL_THRESHOLD = 20.0
SMOKE_OBSCURATION_THRESHOLD = 15.0
CROWD_SIZE_THRESHOLD = 4
RUNNING_HEART_RATE_BPM_THRESHOLD = 120.0

PPE_CLASSES = [DetectionClass.HELMET, DetectionClass.VEST, DetectionClass.GLOVES, DetectionClass.MASK]


def _stable_bbox(seed: str) -> BoundingBox:
    """No real frame exists for a synthetic detection, so the bounding box is
    a deterministic pseudo-random placeholder derived from the object's own
    id -- stable across ticks (doesn't jitter every frame while the same
    object keeps being detected) but distinct per object, rather than a
    meaningless fixed rectangle repeated for everything."""
    digest = hashlib.sha1(seed.encode()).digest()
    x = 0.05 + (digest[0] / 255) * 0.7
    w = 0.12 + (digest[2] / 255) * 0.18
    y = 0.05 + (digest[1] / 255) * (0.95 - 0.05 - (0.12 + (digest[3] / 255) * 0.18))
    h = 0.12 + (digest[3] / 255) * 0.18
    return BoundingBox(x=round(x, 4), y=round(y, 4), width=round(w, 4), height=round(h, 4))


def detect_from_snapshot(snapshot: dict) -> list[Detection]:
    detections: list[Detection] = []

    for zone in snapshot["zones"]:
        zone_id = zone["zone_id"]
        camera_id = zone["camera"]["camera_id"]
        event_type = zone["camera"]["event_type"]
        camera_confidence = zone["camera"]["confidence"]
        person_count = zone["camera"]["person_count"]
        gas_pct_lel = zone["ambient"]["gas_pct_lel"]
        smoke_pct = zone["ambient"]["smoke_pct_obscuration"]

        if event_type in ("fire_detected", "explosion_detected"):
            detections.append(
                Detection(
                    DetectionClass.FIRE,
                    camera_confidence,
                    _stable_bbox(f"{zone_id}:fire"),
                    camera_id,
                    zone_id,
                    metadata={"camera_event": event_type},
                )
            )

        if smoke_pct > SMOKE_OBSCURATION_THRESHOLD:
            conf = min(0.99, 0.5 + smoke_pct / 200)
            detections.append(
                Detection(
                    DetectionClass.SMOKE, conf, _stable_bbox(f"{zone_id}:smoke"), camera_id, zone_id,
                    metadata={"smoke_pct_obscuration": smoke_pct},
                )
            )

        if event_type == "gas_leak_detected" or gas_pct_lel > GAS_LEL_THRESHOLD:
            conf = max(camera_confidence, min(0.99, 0.5 + gas_pct_lel / 150))
            detections.append(
                Detection(
                    DetectionClass.GAS_LEAK, conf, _stable_bbox(f"{zone_id}:gas"), camera_id, zone_id,
                    metadata={"gas_pct_lel": gas_pct_lel},
                )
            )

        if event_type == "ppe_violation":
            class_index = int(hashlib.sha1(zone_id.encode()).hexdigest(), 16) % len(PPE_CLASSES)
            ppe_class = PPE_CLASSES[class_index]
            detections.append(
                Detection(
                    ppe_class, camera_confidence, _stable_bbox(f"{zone_id}:ppe"), camera_id, zone_id,
                    metadata={"camera_event": event_type},
                )
            )

        if person_count > 0:
            detections.append(
                Detection(
                    DetectionClass.WORKER, 0.9, _stable_bbox(f"{zone_id}:worker"), camera_id, zone_id,
                    metadata={"person_count": person_count},
                )
            )

        if person_count >= CROWD_SIZE_THRESHOLD:
            detections.append(
                Detection(
                    DetectionClass.CROWD, min(0.99, 0.6 + person_count * 0.05), _stable_bbox(f"{zone_id}:crowd"),
                    camera_id, zone_id, metadata={"person_count": person_count},
                )
            )

        for eq in zone["equipment"]:
            if eq["status"] == "fault":
                detections.append(
                    Detection(
                        DetectionClass.MACHINE_OBSTRUCTION, 0.85, _stable_bbox(f"{eq['equipment_id']}:obstruction"),
                        camera_id, zone_id, object_id=eq["equipment_id"], metadata={"equipment_status": eq["status"]},
                    )
                )

    zone_by_id = {z["zone_id"]: z for z in snapshot["zones"]}

    for vehicle in snapshot["vehicles"]:
        if vehicle["vehicle_type"] != "forklift":
            continue
        zone = zone_by_id[vehicle["zone_id"]]
        conf = 0.92 if vehicle["status"] == "moving" else 0.8
        detections.append(
            Detection(
                DetectionClass.FORKLIFT, conf, _stable_bbox(f"{vehicle['vehicle_id']}:forklift"),
                zone["camera"]["camera_id"], vehicle["zone_id"], object_id=vehicle["vehicle_id"],
                metadata={"vehicle_status": vehicle["status"]},
            )
        )

    for worker in snapshot["workers"]:
        zone = zone_by_id[worker["zone_id"]]
        camera_id = zone["camera"]["camera_id"]

        if worker["status"] == "collapsed":
            detections.append(
                Detection(
                    DetectionClass.FALLEN_WORKER, 0.93, _stable_bbox(f"{worker['worker_id']}:fallen"),
                    camera_id, worker["zone_id"], object_id=worker["worker_id"],
                    metadata={"worker_status": worker["status"]},
                )
            )
            continue  # a collapsed worker cannot also be running

        heart_rate = worker["vitals"].get("heart_rate_bpm")
        if heart_rate is not None and heart_rate > RUNNING_HEART_RATE_BPM_THRESHOLD:
            conf = min(0.95, 0.55 + (heart_rate - RUNNING_HEART_RATE_BPM_THRESHOLD) / 100)
            detections.append(
                Detection(
                    DetectionClass.RUNNING_WORKER, conf, _stable_bbox(f"{worker['worker_id']}:running"),
                    camera_id, worker["zone_id"], object_id=worker["worker_id"],
                    metadata={"heart_rate_bpm": heart_rate},
                )
            )

    return detections
