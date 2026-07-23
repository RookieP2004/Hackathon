from __future__ import annotations


async def test_list_maintenance_requires_authentication(client):
    response = await client.get("/maintenance")
    assert response.status_code == 401


async def test_create_record_success(client, make_user, equipment_id_factory, maintenance_type_id_factory):
    _admin, headers = await make_user(role="maintenance_engineer")
    equipment_id = await equipment_id_factory()
    maintenance_type_id = await maintenance_type_id_factory("Preventive")

    response = await client.post(
        "/maintenance",
        headers=headers,
        json={"equipment_id": equipment_id, "maintenance_type_id": maintenance_type_id, "description": "Quarterly lube service"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["description"] == "Quarterly lube service"


async def test_create_record_requires_write_role(client, make_user, equipment_id_factory, maintenance_type_id_factory):
    _viewer, headers = await make_user(role="operator")
    equipment_id = await equipment_id_factory()
    maintenance_type_id = await maintenance_type_id_factory("Preventive")

    response = await client.post(
        "/maintenance", headers=headers,
        json={"equipment_id": equipment_id, "maintenance_type_id": maintenance_type_id, "description": "x"},
    )
    assert response.status_code == 403


async def test_get_record_not_found(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/maintenance/999999999", headers=headers)
    assert response.status_code == 404


async def test_complete_record_success(client, make_user, equipment_id_factory, maintenance_type_id_factory):
    _admin, headers = await make_user(role="maintenance_engineer")
    equipment_id = await equipment_id_factory()
    maintenance_type_id = await maintenance_type_id_factory("Preventive")

    create_resp = await client.post(
        "/maintenance", headers=headers,
        json={"equipment_id": equipment_id, "maintenance_type_id": maintenance_type_id, "description": "Bearing replacement"},
    )
    record_id = create_resp.json()["id"]

    complete_resp = await client.post(
        f"/maintenance/{record_id}/complete", headers=headers,
        json={"findings": "Bearing was worn beyond spec", "parts_used": ["bearing-6205"], "cost": 450.0},
    )
    assert complete_resp.status_code == 200
    body = complete_resp.json()
    assert body["status"] == "completed"
    assert body["findings"] == "Bearing was worn beyond spec"
    assert body["completed_at"] is not None


async def test_complete_already_completed_record_returns_422(client, make_user, equipment_id_factory, maintenance_type_id_factory):
    _admin, headers = await make_user(role="maintenance_engineer")
    equipment_id = await equipment_id_factory()
    maintenance_type_id = await maintenance_type_id_factory("Preventive")

    create_resp = await client.post(
        "/maintenance", headers=headers,
        json={"equipment_id": equipment_id, "maintenance_type_id": maintenance_type_id, "description": "x"},
    )
    record_id = create_resp.json()["id"]

    await client.post(f"/maintenance/{record_id}/complete", headers=headers, json={"findings": "ok"})
    second = await client.post(f"/maintenance/{record_id}/complete", headers=headers, json={"findings": "ok again"})
    assert second.status_code == 422


async def test_cancel_record_success(client, make_user, equipment_id_factory, maintenance_type_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    equipment_id = await equipment_id_factory()
    maintenance_type_id = await maintenance_type_id_factory("Preventive")

    create_resp = await client.post(
        "/maintenance", headers=headers,
        json={"equipment_id": equipment_id, "maintenance_type_id": maintenance_type_id, "description": "x"},
    )
    record_id = create_resp.json()["id"]

    response = await client.post(f"/maintenance/{record_id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


async def test_update_terminal_record_returns_422(client, make_user, equipment_id_factory, maintenance_type_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    equipment_id = await equipment_id_factory()
    maintenance_type_id = await maintenance_type_id_factory("Preventive")

    create_resp = await client.post(
        "/maintenance", headers=headers,
        json={"equipment_id": equipment_id, "maintenance_type_id": maintenance_type_id, "description": "x"},
    )
    record_id = create_resp.json()["id"]
    await client.post(f"/maintenance/{record_id}/cancel", headers=headers)

    response = await client.patch(f"/maintenance/{record_id}", headers=headers, json={"description": "changed"})
    assert response.status_code == 422


async def test_filter_maintenance_by_equipment(client, make_user, equipment_id_factory, maintenance_type_id_factory):
    _admin, headers = await make_user(role="maintenance_engineer")
    equipment_a = await equipment_id_factory()
    equipment_b = await equipment_id_factory()
    maintenance_type_id = await maintenance_type_id_factory("Preventive")

    await client.post("/maintenance", headers=headers, json={"equipment_id": equipment_a, "maintenance_type_id": maintenance_type_id, "description": "a"})
    await client.post("/maintenance", headers=headers, json={"equipment_id": equipment_b, "maintenance_type_id": maintenance_type_id, "description": "b"})

    response = await client.get(f"/maintenance?equipment_id={equipment_a}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(r["equipment_id"] == equipment_a for r in body["items"])
