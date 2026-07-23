from __future__ import annotations


async def test_list_incidents_requires_authentication(client):
    response = await client.get("/incidents")
    assert response.status_code == 401


async def test_create_incident_success(client, make_user, plant_id_factory):
    _operator, headers = await make_user(role="operator")
    plant_id = await plant_id_factory()

    response = await client.post(
        "/incidents",
        headers=headers,
        json={"incident_number": "INC-1001", "plant_id": plant_id, "severity": "high"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert body["severity"] == "high"


async def test_create_incident_invalid_severity_returns_422(client, make_user, plant_id_factory):
    _operator, headers = await make_user(role="operator")
    plant_id = await plant_id_factory()

    response = await client.post(
        "/incidents", headers=headers,
        json={"incident_number": "INC-BADSEV", "plant_id": plant_id, "severity": "catastrophic"},
    )
    assert response.status_code == 422


async def test_create_incident_duplicate_number_conflicts(client, make_user, plant_id_factory):
    _operator, headers = await make_user(role="operator")
    plant_id = await plant_id_factory()
    payload = {"incident_number": "INC-DUP", "plant_id": plant_id, "severity": "low"}

    first = await client.post("/incidents", headers=headers, json=payload)
    assert first.status_code == 201
    second = await client.post("/incidents", headers=headers, json=payload)
    assert second.status_code == 409


async def test_get_incident_not_found(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/incidents/999999999", headers=headers)
    assert response.status_code == 404


async def test_full_incident_lifecycle(client, make_user, plant_id_factory):
    _operator, op_headers = await make_user(role="operator")
    _safety, safety_headers = await make_user(role="safety_officer")
    plant_id = await plant_id_factory()

    create_resp = await client.post(
        "/incidents", headers=op_headers,
        json={"incident_number": "INC-LIFECYCLE", "plant_id": plant_id, "severity": "medium"},
    )
    incident_id = create_resp.json()["id"]

    ack_resp = await client.post(f"/incidents/{incident_id}/acknowledge", headers=safety_headers)
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "acknowledged"

    escalate_resp = await client.post(f"/incidents/{incident_id}/escalate", headers=safety_headers)
    assert escalate_resp.status_code == 200
    assert escalate_resp.json()["status"] == "escalated"

    close_resp = await client.post(
        f"/incidents/{incident_id}/close", headers=safety_headers, json={"root_cause": "Worn gasket failed under pressure"}
    )
    assert close_resp.status_code == 200
    body = close_resp.json()
    assert body["status"] == "closed"
    assert body["root_cause"] == "Worn gasket failed under pressure"

    reclose_resp = await client.post(
        f"/incidents/{incident_id}/close", headers=safety_headers, json={"root_cause": "duplicate close attempt"}
    )
    assert reclose_resp.status_code == 422

    timeline_resp = await client.get(f"/incidents/{incident_id}/timeline", headers=safety_headers)
    assert timeline_resp.status_code == 200
    events = [e["event_type"] for e in timeline_resp.json()["items"]]
    assert events == ["created", "acknowledged", "escalated", "closed"]


async def test_add_custom_timeline_event(client, make_user, plant_id_factory):
    _operator, op_headers = await make_user(role="operator")
    _safety, safety_headers = await make_user(role="safety_officer")
    plant_id = await plant_id_factory()

    create_resp = await client.post(
        "/incidents", headers=op_headers,
        json={"incident_number": "INC-CUSTOM-EVENT", "plant_id": plant_id, "severity": "critical"},
    )
    incident_id = create_resp.json()["id"]

    response = await client.post(
        f"/incidents/{incident_id}/timeline", headers=safety_headers,
        json={"event_type": "evacuation_activated", "event_data": {"zone_id": 3, "reason": "critical explosion risk"}, "actor_type": "agent"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["event_type"] == "evacuation_activated"
    assert body["event_data"] == {"zone_id": 3, "reason": "critical explosion risk"}

    timeline_resp = await client.get(f"/incidents/{incident_id}/timeline", headers=safety_headers)
    events = [e["event_type"] for e in timeline_resp.json()["items"]]
    assert events == ["created", "evacuation_activated"]


async def test_add_timeline_event_for_unknown_incident_returns_404(client, make_user):
    _safety, headers = await make_user(role="safety_officer")
    response = await client.post(
        "/incidents/999999999/timeline", headers=headers, json={"event_type": "test_event"}
    )
    assert response.status_code == 404


async def test_acknowledge_incident_not_open_returns_422(client, make_user, plant_id_factory):
    _operator, op_headers = await make_user(role="operator")
    _safety, safety_headers = await make_user(role="safety_officer")
    plant_id = await plant_id_factory()

    create_resp = await client.post(
        "/incidents", headers=op_headers, json={"incident_number": "INC-DOUBLEACK", "plant_id": plant_id, "severity": "low"}
    )
    incident_id = create_resp.json()["id"]

    await client.post(f"/incidents/{incident_id}/acknowledge", headers=safety_headers)
    second = await client.post(f"/incidents/{incident_id}/acknowledge", headers=safety_headers)
    assert second.status_code == 422


async def test_acknowledge_requires_write_role(client, make_user, plant_id_factory):
    _operator, op_headers = await make_user(role="operator")
    plant_id = await plant_id_factory()

    create_resp = await client.post(
        "/incidents", headers=op_headers, json={"incident_number": "INC-NOAUTH", "plant_id": plant_id, "severity": "low"}
    )
    incident_id = create_resp.json()["id"]

    response = await client.post(f"/incidents/{incident_id}/acknowledge", headers=op_headers)
    assert response.status_code == 403


async def test_filter_incidents_by_severity(client, make_user, plant_id_factory):
    _operator, headers = await make_user(role="operator")
    plant_id = await plant_id_factory()

    await client.post("/incidents", headers=headers, json={"incident_number": "INC-SEV1", "plant_id": plant_id, "severity": "critical"})
    await client.post("/incidents", headers=headers, json={"incident_number": "INC-SEV2", "plant_id": plant_id, "severity": "low"})

    response = await client.get("/incidents?severity=critical", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(i["severity"] == "critical" for i in body["items"])
    assert any(i["incident_number"] == "INC-SEV1" for i in body["items"])
