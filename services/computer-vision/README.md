# computer-vision

CV inference pipelines, Vision Agent's Core, per AGENT_ARCHITECTURE.md section 2.

Detects 13 classes (Helmet, Vest, Gloves, Mask, Worker, Forklift, Fire, Smoke,
Gas Leak, Fallen Worker, Running Worker, Crowd, Machine Obstruction) via two
paths:

- **`POST /vision/detect`** — real `ultralytics` YOLOv8n inference on an
  uploaded image. Only `person -> Worker` is mapped from COCO's classes; the
  rest have no COCO equivalent (see `app/vision/yolo_detector.py`).
- **Live simulated pipeline** — connects to iot-simulator's WebSocket
  telemetry feed as its "camera feed" and derives the remaining 12 classes
  from the simulation's own real ground truth (worker status, camera events,
  equipment faults, vehicle list, worker vitals) rather than fabricating
  detections. See `app/vision/synthetic_detector.py`.

Every detection passes through a temporal-persistence gate
(`app/vision/persistence.py`, 3 consecutive ticks) before it's confirmed. A
confirmed episode raises a real Alert (`notification-service`) for
fast-path classes (fire/smoke/gas leak/fallen worker/machine
obstruction/PPE violations) and always submits a real risk score
(`predictive-risk-engine`) — the "Integrate with Risk Engine" requirement.

- **`GET /vision/live`** — currently-confirmed detections.
- **`GET /vision/events`** — recent confirmed episodes (event log).

**Local dev:** `cd services/computer-vision && poetry install && poetry run uvicorn app.main:app --reload`
