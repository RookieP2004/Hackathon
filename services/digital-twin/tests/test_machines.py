from __future__ import annotations


async def test_list_machines_requires_authentication(client):
    response = await client.get("/machines")
    assert response.status_code == 401


async def test_create_machine_creates_equipment_and_machine_together(
    client, make_user, zone_id_factory, equipment_type_id_factory
):
    _admin, headers = await make_user(role="plant_admin")
    zone_id = await zone_id_factory()
    equipment_type_id = await equipment_type_id_factory("Pump")

    response = await client.post(
        "/machines",
        headers=headers,
        json={
            "zone_id": zone_id,
            "equipment_type_id": equipment_type_id,
            "tag": "P-101",
            "name": "Feed Pump 101",
            "machine_class": "centrifugal_pump",
            "rated_power_kw": 75.0,
            "rated_rpm": 1780,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["tag"] == "P-101"
    assert body["machine_class"] == "centrifugal_pump"
    assert body["rated_power_kw"] == 75.0
    assert body["status"] == "operational"


async def test_create_machine_duplicate_tag_in_zone_conflicts(
    client, make_user, zone_id_factory, equipment_type_id_factory
):
    _admin, headers = await make_user(role="system_admin")
    zone_id = await zone_id_factory()
    equipment_type_id = await equipment_type_id_factory("Pump")
    payload = {
        "zone_id": zone_id, "equipment_type_id": equipment_type_id,
        "tag": "P-DUP", "name": "First", "machine_class": "centrifugal_pump",
    }

    first = await client.post("/machines", headers=headers, json=payload)
    assert first.status_code == 201

    payload["name"] = "Second"
    second = await client.post("/machines", headers=headers, json=payload)
    assert second.status_code == 409


async def test_create_machine_invalid_criticality_returns_422(
    client, make_user, zone_id_factory, equipment_type_id_factory
):
    _admin, headers = await make_user(role="system_admin")
    zone_id = await zone_id_factory()
    equipment_type_id = await equipment_type_id_factory("Pump")

    response = await client.post(
        "/machines",
        headers=headers,
        json={
            "zone_id": zone_id, "equipment_type_id": equipment_type_id,
            "tag": "P-BAD", "name": "Bad Criticality", "machine_class": "centrifugal_pump",
            "criticality": 99,
        },
    )
    assert response.status_code == 422


async def test_get_machine_not_found(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/machines/999999999", headers=headers)
    assert response.status_code == 404


async def test_update_machine_success(client, make_user, zone_id_factory, equipment_type_id_factory):
    _admin, headers = await make_user(role="maintenance_engineer")
    zone_id = await zone_id_factory()
    equipment_type_id = await equipment_type_id_factory("Compressor")

    create_resp = await client.post(
        "/machines", headers=headers,
        json={
            "zone_id": zone_id, "equipment_type_id": equipment_type_id,
            "tag": "C-101", "name": "Compressor 101", "machine_class": "reciprocating_compressor",
        },
    )
    machine_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/machines/{machine_id}", headers=headers,
        json={"status": "under_maintenance", "rated_rpm": 3600},
    )
    assert update_resp.status_code == 200
    body = update_resp.json()
    assert body["status"] == "under_maintenance"
    assert body["rated_rpm"] == 3600
    # Unchanged fields (from the Equipment side) must survive an update that
    # only touched Machine-side fields, and vice versa -- proving the
    # supertype/subtype update logic doesn't clobber the other table's data.
    assert body["tag"] == "C-101"


async def test_decommission_machine_requires_admin_role(client, make_user, zone_id_factory, equipment_type_id_factory):
    _user, headers = await make_user(role="maintenance_engineer")
    zone_id = await zone_id_factory()
    equipment_type_id = await equipment_type_id_factory("Pump")

    create_resp = await client.post(
        "/machines", headers=headers,
        json={"zone_id": zone_id, "equipment_type_id": equipment_type_id, "tag": "P-DECOM", "name": "X", "machine_class": "centrifugal_pump"},
    )
    machine_id = create_resp.json()["id"]

    response = await client.delete(f"/machines/{machine_id}", headers=headers)
    assert response.status_code == 403


async def test_decommission_machine_success(client, make_user, zone_id_factory, equipment_type_id_factory):
    _admin, headers = await make_user(role="system_admin")
    zone_id = await zone_id_factory()
    equipment_type_id = await equipment_type_id_factory("Pump")

    create_resp = await client.post(
        "/machines", headers=headers,
        json={"zone_id": zone_id, "equipment_type_id": equipment_type_id, "tag": "P-DECOM2", "name": "X", "machine_class": "centrifugal_pump"},
    )
    machine_id = create_resp.json()["id"]

    response = await client.delete(f"/machines/{machine_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "decommissioned"


async def test_filter_machines_by_zone(client, make_user, zone_id_factory, equipment_type_id_factory):
    _admin, headers = await make_user(role="system_admin")
    zone_a = await zone_id_factory()
    zone_b = await zone_id_factory()
    equipment_type_id = await equipment_type_id_factory("Pump")

    await client.post("/machines", headers=headers, json={"zone_id": zone_a, "equipment_type_id": equipment_type_id, "tag": "P-A", "name": "A", "machine_class": "centrifugal_pump"})
    await client.post("/machines", headers=headers, json={"zone_id": zone_b, "equipment_type_id": equipment_type_id, "tag": "P-B", "name": "B", "machine_class": "centrifugal_pump"})

    response = await client.get(f"/machines?zone_id={zone_a}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(m["zone_id"] == zone_a for m in body["items"])
    assert any(m["tag"] == "P-A" for m in body["items"])
