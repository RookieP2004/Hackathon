from __future__ import annotations


async def test_list_risk_scores_requires_authentication(client):
    response = await client.get("/risk-engine/risk-scores")
    assert response.status_code == 401


async def test_create_risk_score_success(client, make_user, equipment_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    equipment_id = await equipment_id_factory()

    response = await client.post(
        "/risk-engine/risk-scores",
        headers=headers,
        json={"equipment_id": equipment_id, "score": 72.5, "confidence": 0.85, "model_version": "risk-fusion-v1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["score"] == 72.5
    assert body["equipment_id"] == equipment_id


async def test_create_risk_score_without_target_returns_422(client, make_user):
    _admin, headers = await make_user(role="plant_admin")
    response = await client.post(
        "/risk-engine/risk-scores", headers=headers,
        json={"score": 50.0, "confidence": 0.5, "model_version": "risk-fusion-v1"},
    )
    assert response.status_code == 422


async def test_create_risk_score_out_of_range_returns_422(client, make_user, equipment_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    equipment_id = await equipment_id_factory()
    response = await client.post(
        "/risk-engine/risk-scores", headers=headers,
        json={"equipment_id": equipment_id, "score": 150.0, "confidence": 0.5, "model_version": "risk-fusion-v1"},
    )
    assert response.status_code == 422


async def test_create_risk_score_requires_write_role(client, make_user, equipment_id_factory):
    _viewer, headers = await make_user(role="maintenance_engineer")
    equipment_id = await equipment_id_factory()
    response = await client.post(
        "/risk-engine/risk-scores", headers=headers,
        json={"equipment_id": equipment_id, "score": 50.0, "confidence": 0.5, "model_version": "risk-fusion-v1"},
    )
    assert response.status_code == 403


async def test_filter_risk_scores_by_score(client, make_user, equipment_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    equipment_id = await equipment_id_factory()

    await client.post("/risk-engine/risk-scores", headers=headers, json={"equipment_id": equipment_id, "score": 90.0, "confidence": 0.9, "model_version": "v1"})
    await client.post("/risk-engine/risk-scores", headers=headers, json={"equipment_id": equipment_id, "score": 10.0, "confidence": 0.9, "model_version": "v1"})

    response = await client.get("/risk-engine/risk-scores?score_gte=50", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(r["score"] >= 50 for r in body["items"])


async def test_create_and_get_prediction(client, make_user, equipment_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    equipment_id = await equipment_id_factory()

    create_resp = await client.post(
        "/risk-engine/predictions",
        headers=headers,
        json={
            "equipment_id": equipment_id, "model_name": "vibration-lstm", "model_version": "v3",
            "target_metric": "rms_vibration", "predicted_value": 4.2, "confidence": 0.77,
            "prediction_horizon_minutes": 60,
        },
    )
    assert create_resp.status_code == 201
    prediction_id = create_resp.json()["id"]

    get_resp = await client.get(f"/risk-engine/predictions/{prediction_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["actual_outcome"] is None


async def test_get_prediction_not_found(client, make_user):
    _admin, headers = await make_user(role="plant_admin")
    response = await client.get("/risk-engine/predictions/999999999", headers=headers)
    assert response.status_code == 404


async def test_record_prediction_outcome(client, make_user, equipment_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    equipment_id = await equipment_id_factory()

    create_resp = await client.post(
        "/risk-engine/predictions", headers=headers,
        json={
            "equipment_id": equipment_id, "model_name": "vibration-lstm", "model_version": "v3",
            "target_metric": "rms_vibration", "predicted_value": 4.2, "confidence": 0.77,
            "prediction_horizon_minutes": 60,
        },
    )
    prediction_id = create_resp.json()["id"]

    outcome_resp = await client.post(f"/risk-engine/predictions/{prediction_id}/outcome", headers=headers, json={"actual_outcome": 4.5})
    assert outcome_resp.status_code == 200
    body = outcome_resp.json()
    assert body["actual_outcome"] == 4.5
    assert body["outcome_recorded_at"] is not None


async def test_record_outcome_twice_returns_422(client, make_user, equipment_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    equipment_id = await equipment_id_factory()

    create_resp = await client.post(
        "/risk-engine/predictions", headers=headers,
        json={
            "equipment_id": equipment_id, "model_name": "vibration-lstm", "model_version": "v3",
            "target_metric": "rms_vibration", "predicted_value": 4.2, "confidence": 0.77,
            "prediction_horizon_minutes": 60,
        },
    )
    prediction_id = create_resp.json()["id"]

    await client.post(f"/risk-engine/predictions/{prediction_id}/outcome", headers=headers, json={"actual_outcome": 4.5})
    second = await client.post(f"/risk-engine/predictions/{prediction_id}/outcome", headers=headers, json={"actual_outcome": 5.0})
    assert second.status_code == 422
