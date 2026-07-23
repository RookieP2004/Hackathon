from __future__ import annotations


async def test_list_sensors_requires_authentication(client):
    response = await client.get("/sensors")
    assert response.status_code == 401


async def test_create_sensor_success(client, make_user, zone_id_factory, sensor_type_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    zone_id = await zone_id_factory()
    sensor_type_id = await sensor_type_id_factory("Vibration")

    response = await client.post(
        "/sensors",
        headers=headers,
        json={
            "sensor_type_id": sensor_type_id,
            "zone_id": zone_id,
            "tag": "VIB-101",
            "unit": "mm/s",
            "protocol": "mqtt",
            "sample_rate_hz": 10.0,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["tag"] == "VIB-101"
    assert body["status"] == "active"


async def test_create_sensor_without_target_returns_422(client, make_user, sensor_type_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    sensor_type_id = await sensor_type_id_factory("Vibration")

    response = await client.post(
        "/sensors",
        headers=headers,
        json={"sensor_type_id": sensor_type_id, "tag": "VIB-NOTARGET", "unit": "mm/s", "protocol": "mqtt"},
    )
    assert response.status_code == 422


async def test_create_sensor_invalid_protocol_returns_422(client, make_user, zone_id_factory, sensor_type_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    zone_id = await zone_id_factory()
    sensor_type_id = await sensor_type_id_factory("Vibration")

    response = await client.post(
        "/sensors",
        headers=headers,
        json={
            "sensor_type_id": sensor_type_id, "zone_id": zone_id,
            "tag": "VIB-BADPROTO", "unit": "mm/s", "protocol": "carrier_pigeon",
        },
    )
    assert response.status_code == 422


async def test_create_sensor_duplicate_tag_conflicts(client, make_user, zone_id_factory, sensor_type_id_factory):
    _admin, headers = await make_user(role="system_admin")
    zone_id = await zone_id_factory()
    sensor_type_id = await sensor_type_id_factory("Vibration")
    payload = {"sensor_type_id": sensor_type_id, "zone_id": zone_id, "tag": "VIB-DUP", "unit": "mm/s", "protocol": "mqtt"}

    first = await client.post("/sensors", headers=headers, json=payload)
    assert first.status_code == 201
    second = await client.post("/sensors", headers=headers, json=payload)
    assert second.status_code == 409


async def test_get_sensor_not_found(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/sensors/999999999", headers=headers)
    assert response.status_code == 404


async def test_update_sensor_success(client, make_user, zone_id_factory, sensor_type_id_factory):
    _admin, headers = await make_user(role="maintenance_engineer")
    zone_id = await zone_id_factory()
    sensor_type_id = await sensor_type_id_factory("Temperature")

    create_resp = await client.post(
        "/sensors", headers=headers,
        json={"sensor_type_id": sensor_type_id, "zone_id": zone_id, "tag": "TEMP-101", "unit": "C", "protocol": "modbus_tcp"},
    )
    sensor_id = create_resp.json()["id"]

    update_resp = await client.patch(f"/sensors/{sensor_id}", headers=headers, json={"status": "faulted"})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "faulted"


async def test_decommission_sensor_requires_write_role(client, make_user, zone_id_factory, sensor_type_id_factory):
    _viewer, viewer_headers = await make_user(role="safety_officer")
    _admin, admin_headers = await make_user(role="system_admin")
    zone_id = await zone_id_factory()
    sensor_type_id = await sensor_type_id_factory("Pressure")

    create_resp = await client.post(
        "/sensors", headers=admin_headers,
        json={"sensor_type_id": sensor_type_id, "zone_id": zone_id, "tag": "PRESS-101", "unit": "bar", "protocol": "opc_ua"},
    )
    sensor_id = create_resp.json()["id"]

    response = await client.delete(f"/sensors/{sensor_id}", headers=viewer_headers)
    assert response.status_code == 403


async def test_ingest_and_list_readings(client, make_user, zone_id_factory, sensor_type_id_factory):
    _admin, headers = await make_user(role="maintenance_engineer")
    zone_id = await zone_id_factory()
    sensor_type_id = await sensor_type_id_factory("Vibration")

    create_resp = await client.post(
        "/sensors", headers=headers,
        json={"sensor_type_id": sensor_type_id, "zone_id": zone_id, "tag": "VIB-READ", "unit": "mm/s", "protocol": "mqtt"},
    )
    sensor_id = create_resp.json()["id"]

    for value in (1.2, 1.5, 1.8):
        ingest_resp = await client.post(
            f"/sensors/{sensor_id}/readings", headers=headers, json={"value": value, "quality": "good"}
        )
        assert ingest_resp.status_code == 201

    list_resp = await client.get(f"/sensors/{sensor_id}/readings", headers=headers)
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 3
    assert all(r["sensor_id"] == sensor_id for r in body["items"])


async def test_ingest_reading_for_unknown_sensor_returns_404(client, make_user):
    _admin, headers = await make_user(role="maintenance_engineer")
    response = await client.post("/sensors/999999999/readings", headers=headers, json={"value": 1.0})
    assert response.status_code == 404


async def test_out_of_range_reading_is_downgraded_to_bad_quality(client, make_user, zone_id_factory, sensor_type_id_factory):
    _admin, headers = await make_user(role="maintenance_engineer")
    zone_id = await zone_id_factory()
    sensor_type_id = await sensor_type_id_factory("Pressure")

    create_resp = await client.post(
        "/sensors", headers=headers,
        json={
            "sensor_type_id": sensor_type_id, "zone_id": zone_id, "tag": "PRESS-RANGE", "unit": "bar",
            "protocol": "opc_ua", "min_range": 0.0, "max_range": 100.0,
        },
    )
    sensor_id = create_resp.json()["id"]

    # Self-reported "good" quality is not trusted once the value is outside
    # the sensor's own calibrated range -- the reading is still recorded
    # (never rejected/excluded), only its quality flag is corrected.
    in_range = await client.post(f"/sensors/{sensor_id}/readings", headers=headers, json={"value": 50.0, "quality": "good"})
    assert in_range.json()["quality"] == "good"

    out_of_range = await client.post(f"/sensors/{sensor_id}/readings", headers=headers, json={"value": 999.0, "quality": "good"})
    assert out_of_range.status_code == 201
    assert out_of_range.json()["quality"] == "bad"

    # A caller-reported "uncertain"/"bad" reading is left as-is, never
    # silently upgraded just because it happens to be in-range.
    already_flagged = await client.post(f"/sensors/{sensor_id}/readings", headers=headers, json={"value": 50.0, "quality": "uncertain"})
    assert already_flagged.json()["quality"] == "uncertain"


async def test_filter_sensors_by_zone(client, make_user, zone_id_factory, sensor_type_id_factory):
    _admin, headers = await make_user(role="system_admin")
    zone_a = await zone_id_factory()
    zone_b = await zone_id_factory()
    sensor_type_id = await sensor_type_id_factory("Vibration")

    await client.post("/sensors", headers=headers, json={"sensor_type_id": sensor_type_id, "zone_id": zone_a, "tag": "S-A", "unit": "mm/s", "protocol": "mqtt"})
    await client.post("/sensors", headers=headers, json={"sensor_type_id": sensor_type_id, "zone_id": zone_b, "tag": "S-B", "unit": "mm/s", "protocol": "mqtt"})

    response = await client.get(f"/sensors?zone_id={zone_a}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(s["zone_id"] == zone_a for s in body["items"])
    assert any(s["tag"] == "S-A" for s in body["items"])


async def test_list_sensors_invalid_sort_field_returns_400(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/sensors?sort=not_a_real_field", headers=headers)
    assert response.status_code == 400
