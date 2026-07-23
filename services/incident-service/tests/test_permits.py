from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _window():
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=8)
    return start.isoformat(), end.isoformat()


async def test_list_permits_requires_authentication(client):
    response = await client.get("/permits")
    assert response.status_code == 401


async def test_create_permit_success(client, make_user, zone_id_factory, worker_id_factory, permit_type_id_factory):
    _admin, headers = await make_user(role="safety_officer")
    zone_id = await zone_id_factory()
    worker_id = await worker_id_factory()
    permit_type_id = await permit_type_id_factory("Hot Work")
    valid_from, valid_to = _window()

    response = await client.post(
        "/permits",
        headers=headers,
        json={
            "permit_number": "PTW-1001",
            "permit_type_id": permit_type_id,
            "worker_id": worker_id,
            "zone_id": zone_id,
            "valid_from": valid_from,
            "valid_to": valid_to,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["permit_number"] == "PTW-1001"


async def test_create_permit_invalid_window_returns_422(client, make_user, zone_id_factory, worker_id_factory, permit_type_id_factory):
    _admin, headers = await make_user(role="safety_officer")
    zone_id = await zone_id_factory()
    worker_id = await worker_id_factory()
    permit_type_id = await permit_type_id_factory("Hot Work")
    valid_from, valid_to = _window()

    response = await client.post(
        "/permits", headers=headers,
        json={
            "permit_number": "PTW-BAD", "permit_type_id": permit_type_id, "worker_id": worker_id, "zone_id": zone_id,
            "valid_from": valid_to, "valid_to": valid_from,
        },
    )
    assert response.status_code == 422


async def test_create_permit_duplicate_number_conflicts(client, make_user, zone_id_factory, worker_id_factory, permit_type_id_factory):
    _admin, headers = await make_user(role="system_admin")
    zone_id = await zone_id_factory()
    worker_id = await worker_id_factory()
    permit_type_id = await permit_type_id_factory("Hot Work")
    valid_from, valid_to = _window()
    payload = {
        "permit_number": "PTW-DUP", "permit_type_id": permit_type_id, "worker_id": worker_id, "zone_id": zone_id,
        "valid_from": valid_from, "valid_to": valid_to,
    }

    first = await client.post("/permits", headers=headers, json=payload)
    assert first.status_code == 201
    second = await client.post("/permits", headers=headers, json=payload)
    assert second.status_code == 409


async def test_get_permit_not_found(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/permits/999999999", headers=headers)
    assert response.status_code == 404


async def test_update_permit_status(client, make_user, zone_id_factory, worker_id_factory, permit_type_id_factory):
    _admin, headers = await make_user(role="safety_officer")
    zone_id = await zone_id_factory()
    worker_id = await worker_id_factory()
    permit_type_id = await permit_type_id_factory("Confined Space")
    valid_from, valid_to = _window()

    create_resp = await client.post(
        "/permits", headers=headers,
        json={
            "permit_number": "PTW-ACT", "permit_type_id": permit_type_id, "worker_id": worker_id, "zone_id": zone_id,
            "valid_from": valid_from, "valid_to": valid_to,
        },
    )
    permit_id = create_resp.json()["id"]

    update_resp = await client.patch(f"/permits/{permit_id}", headers=headers, json={"status": "active"})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "active"


async def test_revoke_permit_success(client, make_user, zone_id_factory, worker_id_factory, permit_type_id_factory):
    _admin, headers = await make_user(role="system_admin")
    zone_id = await zone_id_factory()
    worker_id = await worker_id_factory()
    permit_type_id = await permit_type_id_factory("Hot Work")
    valid_from, valid_to = _window()

    create_resp = await client.post(
        "/permits", headers=headers,
        json={
            "permit_number": "PTW-REV", "permit_type_id": permit_type_id, "worker_id": worker_id, "zone_id": zone_id,
            "valid_from": valid_from, "valid_to": valid_to,
        },
    )
    permit_id = create_resp.json()["id"]

    response = await client.delete(f"/permits/{permit_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"


async def test_revoke_already_revoked_permit_returns_422(client, make_user, zone_id_factory, worker_id_factory, permit_type_id_factory):
    _admin, headers = await make_user(role="system_admin")
    zone_id = await zone_id_factory()
    worker_id = await worker_id_factory()
    permit_type_id = await permit_type_id_factory("Hot Work")
    valid_from, valid_to = _window()

    create_resp = await client.post(
        "/permits", headers=headers,
        json={
            "permit_number": "PTW-REV2", "permit_type_id": permit_type_id, "worker_id": worker_id, "zone_id": zone_id,
            "valid_from": valid_from, "valid_to": valid_to,
        },
    )
    permit_id = create_resp.json()["id"]

    await client.delete(f"/permits/{permit_id}", headers=headers)
    second = await client.delete(f"/permits/{permit_id}", headers=headers)
    assert second.status_code == 422


async def test_write_action_requires_write_role(client, make_user, zone_id_factory, worker_id_factory, permit_type_id_factory):
    _viewer, headers = await make_user(role="operator")
    zone_id = await zone_id_factory()
    worker_id = await worker_id_factory()
    permit_type_id = await permit_type_id_factory("Hot Work")
    valid_from, valid_to = _window()

    response = await client.post(
        "/permits", headers=headers,
        json={
            "permit_number": "PTW-DENIED", "permit_type_id": permit_type_id, "worker_id": worker_id, "zone_id": zone_id,
            "valid_from": valid_from, "valid_to": valid_to,
        },
    )
    assert response.status_code == 403


async def test_filter_permits_by_status(client, make_user, zone_id_factory, worker_id_factory, permit_type_id_factory):
    _admin, headers = await make_user(role="system_admin")
    zone_id = await zone_id_factory()
    worker_id = await worker_id_factory()
    permit_type_id = await permit_type_id_factory("Hot Work")
    valid_from, valid_to = _window()

    await client.post(
        "/permits", headers=headers,
        json={
            "permit_number": "PTW-F1", "permit_type_id": permit_type_id, "worker_id": worker_id, "zone_id": zone_id,
            "valid_from": valid_from, "valid_to": valid_to,
        },
    )

    response = await client.get("/permits?status=draft", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(p["status"] == "draft" for p in body["items"])
    assert any(p["permit_number"] == "PTW-F1" for p in body["items"])
