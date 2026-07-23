from __future__ import annotations


async def test_list_playbooks_requires_authentication(client):
    response = await client.get("/emergency/playbooks")
    assert response.status_code == 401


async def test_create_playbook_success(client, make_user):
    _admin, headers = await make_user(role="safety_officer")
    response = await client.post(
        "/emergency/playbooks",
        headers=headers,
        json={"name": "Gas Leak Response", "hazard_class": "toxic_release", "description": "Standard H2S response"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["version"] == 1
    assert body["is_active"] is True


async def test_create_playbook_duplicate_conflicts(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    payload = {"name": "Fire Response", "hazard_class": "fire"}
    first = await client.post("/emergency/playbooks", headers=headers, json=payload)
    assert first.status_code == 201
    second = await client.post("/emergency/playbooks", headers=headers, json=payload)
    assert second.status_code == 409


async def test_get_playbook_not_found(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/emergency/playbooks/999999999", headers=headers)
    assert response.status_code == 404


async def test_deactivate_playbook_success(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    create_resp = await client.post("/emergency/playbooks", headers=headers, json={"name": "Chemical Spill", "hazard_class": "spill"})
    playbook_id = create_resp.json()["id"]

    response = await client.delete(f"/emergency/playbooks/{playbook_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    second = await client.delete(f"/emergency/playbooks/{playbook_id}", headers=headers)
    assert second.status_code == 422


async def test_add_playbook_step_and_list(client, make_user):
    _admin, headers = await make_user(role="safety_officer")
    create_resp = await client.post("/emergency/playbooks", headers=headers, json={"name": "Evacuation", "hazard_class": "structural"})
    playbook_id = create_resp.json()["id"]

    step_resp = await client.post(
        f"/emergency/playbooks/{playbook_id}/steps",
        headers=headers,
        json={"step_order": 1, "description": "Sound evacuation alarm", "autonomy_tier": "tier_2_execute_notify", "tool_name": "alarm_system"},
    )
    assert step_resp.status_code == 201

    dup_resp = await client.post(
        f"/emergency/playbooks/{playbook_id}/steps",
        headers=headers,
        json={"step_order": 1, "description": "Duplicate order", "autonomy_tier": "tier_1_recommend", "tool_name": "x"},
    )
    assert dup_resp.status_code == 409

    list_resp = await client.get(f"/emergency/playbooks/{playbook_id}/steps", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


async def test_create_playbook_step_invalid_autonomy_tier_returns_422(client, make_user):
    _admin, headers = await make_user(role="safety_officer")
    create_resp = await client.post("/emergency/playbooks", headers=headers, json={"name": "Test PB", "hazard_class": "test"})
    playbook_id = create_resp.json()["id"]

    response = await client.post(
        f"/emergency/playbooks/{playbook_id}/steps",
        headers=headers,
        json={"step_order": 1, "description": "x", "autonomy_tier": "tier_99_bogus", "tool_name": "x"},
    )
    assert response.status_code == 422


async def test_initiate_and_resolve_emergency_event(client, make_user, plant_id_factory):
    _team, headers = await make_user(role="emergency_team")
    plant_id = await plant_id_factory()

    create_resp = await client.post(
        "/emergency/events", headers=headers,
        json={"plant_id": plant_id, "event_type": "gas_leak"},
    )
    assert create_resp.status_code == 201
    event_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "initiated"

    resolve_resp = await client.post(f"/emergency/events/{event_id}/resolve", headers=headers)
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"

    second_resolve = await client.post(f"/emergency/events/{event_id}/resolve", headers=headers)
    assert second_resolve.status_code == 422


async def test_create_event_requires_write_role(client, make_user, plant_id_factory):
    _viewer, headers = await make_user(role="operator")
    plant_id = await plant_id_factory()

    response = await client.post("/emergency/events", headers=headers, json={"plant_id": plant_id, "event_type": "gas_leak"})
    assert response.status_code == 403


async def test_event_step_approval_flow(client, make_user, plant_id_factory):
    _team, headers = await make_user(role="emergency_team")
    plant_id = await plant_id_factory()

    event_resp = await client.post("/emergency/events", headers=headers, json={"plant_id": plant_id, "event_type": "fire"})
    event_id = event_resp.json()["id"]

    step_resp = await client.post(f"/emergency/events/{event_id}/steps", headers=headers, json={})
    assert step_resp.status_code == 201
    step_id = step_resp.json()["id"]
    assert step_resp.json()["status"] == "pending"

    approve_resp = await client.post(f"/emergency/events/steps/{step_id}/approve", headers=headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    reapprove_resp = await client.post(f"/emergency/events/steps/{step_id}/approve", headers=headers)
    assert reapprove_resp.status_code == 422

    complete_resp = await client.post(
        f"/emergency/events/steps/{step_id}/complete", headers=headers, json={"result": {"alarm": "sounded"}, "success": True}
    )
    assert complete_resp.status_code == 200
    body = complete_resp.json()
    assert body["status"] == "completed"
    assert body["result"] == {"alarm": "sounded"}


async def test_reject_event_step(client, make_user, plant_id_factory):
    _team, headers = await make_user(role="emergency_team")
    plant_id = await plant_id_factory()

    event_resp = await client.post("/emergency/events", headers=headers, json={"plant_id": plant_id, "event_type": "fire"})
    event_id = event_resp.json()["id"]

    step_resp = await client.post(f"/emergency/events/{event_id}/steps", headers=headers, json={})
    step_id = step_resp.json()["id"]

    reject_resp = await client.post(f"/emergency/events/steps/{step_id}/reject", headers=headers)
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"


async def test_complete_step_without_approval_returns_422(client, make_user, plant_id_factory):
    _team, headers = await make_user(role="emergency_team")
    plant_id = await plant_id_factory()

    event_resp = await client.post("/emergency/events", headers=headers, json={"plant_id": plant_id, "event_type": "fire"})
    event_id = event_resp.json()["id"]

    step_resp = await client.post(f"/emergency/events/{event_id}/steps", headers=headers, json={})
    step_id = step_resp.json()["id"]

    response = await client.post(f"/emergency/events/steps/{step_id}/complete", headers=headers, json={"success": True})
    assert response.status_code == 422


async def test_filter_events_by_status(client, make_user, plant_id_factory):
    _team, headers = await make_user(role="emergency_team")
    plant_id = await plant_id_factory()

    await client.post("/emergency/events", headers=headers, json={"plant_id": plant_id, "event_type": "gas_leak"})

    response = await client.get("/emergency/events?status=initiated", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(e["status"] == "initiated" for e in body["items"])
