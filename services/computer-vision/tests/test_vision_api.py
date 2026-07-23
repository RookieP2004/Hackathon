from pathlib import Path

import asyncpg
import pytest
import ultralytics
from fastapi.testclient import TestClient
from jose import jwt

from app.main import create_app

_ZIDANE_JPG = Path(ultralytics.__file__).resolve().parent / "assets" / "zidane.jpg"
POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
JWT_SECRET = "changeme_generate_a_real_secret_before_any_shared_deployment"


@pytest.fixture
async def auth_headers() -> dict:
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        row = await conn.fetchrow(
            "SELECT u.id, u.default_role_id FROM users u JOIN roles r ON r.id = u.default_role_id WHERE r.name = 'safety_officer' LIMIT 1"
        )
    finally:
        await conn.close()
    token = jwt.encode({"sub": str(row["id"]), "role_id": row["default_role_id"], "type": "access", "exp": 9999999999}, JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


async def test_vision_endpoints_require_authentication():
    client = TestClient(create_app())
    with open(_ZIDANE_JPG, "rb") as f:
        detect_response = client.post(
            "/vision/detect", params={"camera_id": "CAM-01"}, files={"file": ("zidane.jpg", f, "image/jpeg")},
        )
    assert detect_response.status_code == 401
    assert client.get("/vision/live").status_code == 401
    assert client.get("/vision/events").status_code == 401


async def test_detect_endpoint_runs_real_inference_on_uploaded_image(auth_headers):
    client = TestClient(create_app())
    with open(_ZIDANE_JPG, "rb") as f:
        response = client.post(
            "/vision/detect",
            params={"camera_id": "CAM-01", "zone_id": "compressor-house"},
            files={"file": ("zidane.jpg", f, "image/jpeg")},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["camera_id"] == "CAM-01"
    assert len(body["detections"]) > 0
    assert body["detections"][0]["detection_class"] == "worker"
    assert body["detections"][0]["source"] == "yolo_inference"


async def test_detect_endpoint_rejects_non_image_upload(auth_headers):
    client = TestClient(create_app())
    response = client.post(
        "/vision/detect",
        params={"camera_id": "CAM-01"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_live_and_events_endpoints_are_reachable_once_lifespan_runs(auth_headers):
    with TestClient(create_app()) as client:
        live = client.get("/vision/live", headers=auth_headers)
        events = client.get("/vision/events", headers=auth_headers)

    assert live.status_code == 200
    assert "detections" in live.json()
    assert events.status_code == 200
    assert "events" in events.json()
