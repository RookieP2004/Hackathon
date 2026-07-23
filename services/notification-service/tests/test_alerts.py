from __future__ import annotations


async def test_list_alerts_requires_authentication(client):
    response = await client.get("/alerts")
    assert response.status_code == 401


async def test_create_alert_success(client, make_user):
    _operator, headers = await make_user(role="operator")

    response = await client.post(
        "/alerts",
        headers=headers,
        json={"alert_type": "high_vibration", "severity": "high", "message": "Vibration exceeded threshold on P-101"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert body["severity"] == "high"


async def test_create_alert_invalid_severity_returns_422(client, make_user):
    _operator, headers = await make_user(role="operator")
    response = await client.post(
        "/alerts", headers=headers,
        json={"alert_type": "high_vibration", "severity": "apocalyptic", "message": "x"},
    )
    assert response.status_code == 422


async def test_get_alert_not_found(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/alerts/999999999", headers=headers)
    assert response.status_code == 404


async def test_alert_lifecycle_acknowledge_then_resolve(client, make_user):
    _operator, op_headers = await make_user(role="operator")
    _safety, safety_headers = await make_user(role="safety_officer")

    create_resp = await client.post(
        "/alerts", headers=op_headers,
        json={"alert_type": "gas_leak", "severity": "critical", "message": "H2S detected in Zone 3"},
    )
    alert_id = create_resp.json()["id"]

    ack_resp = await client.post(f"/alerts/{alert_id}/acknowledge", headers=safety_headers)
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "acknowledged"

    resolve_resp = await client.post(f"/alerts/{alert_id}/resolve", headers=safety_headers)
    assert resolve_resp.status_code == 200
    body = resolve_resp.json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None


async def test_acknowledge_non_open_alert_returns_422(client, make_user):
    _operator, op_headers = await make_user(role="operator")
    _safety, safety_headers = await make_user(role="safety_officer")

    create_resp = await client.post(
        "/alerts", headers=op_headers, json={"alert_type": "gas_leak", "severity": "critical", "message": "x"}
    )
    alert_id = create_resp.json()["id"]

    await client.post(f"/alerts/{alert_id}/acknowledge", headers=safety_headers)
    second = await client.post(f"/alerts/{alert_id}/acknowledge", headers=safety_headers)
    assert second.status_code == 422


async def test_resolve_already_resolved_alert_returns_422(client, make_user):
    _operator, op_headers = await make_user(role="operator")
    _safety, safety_headers = await make_user(role="safety_officer")

    create_resp = await client.post(
        "/alerts", headers=op_headers, json={"alert_type": "gas_leak", "severity": "critical", "message": "x"}
    )
    alert_id = create_resp.json()["id"]

    await client.post(f"/alerts/{alert_id}/resolve", headers=safety_headers)
    second = await client.post(f"/alerts/{alert_id}/resolve", headers=safety_headers)
    assert second.status_code == 422


async def test_acknowledge_requires_write_role(client, make_user):
    _operator, op_headers = await make_user(role="operator")
    _viewer, viewer_headers = await make_user(role="government_auditor")

    create_resp = await client.post(
        "/alerts", headers=op_headers, json={"alert_type": "gas_leak", "severity": "low", "message": "x"}
    )
    alert_id = create_resp.json()["id"]

    response = await client.post(f"/alerts/{alert_id}/acknowledge", headers=viewer_headers)
    assert response.status_code == 403


async def test_filter_alerts_by_severity(client, make_user):
    _operator, headers = await make_user(role="operator")

    await client.post("/alerts", headers=headers, json={"alert_type": "a", "severity": "critical", "message": "x"})
    await client.post("/alerts", headers=headers, json={"alert_type": "b", "severity": "low", "message": "y"})

    response = await client.get("/alerts?severity=critical", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(a["severity"] == "critical" for a in body["items"])


async def test_list_alerts_invalid_sort_field_returns_400(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/alerts?sort=not_a_field", headers=headers)
    assert response.status_code == 400
