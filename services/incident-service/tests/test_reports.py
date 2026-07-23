from __future__ import annotations


async def test_list_reports_requires_authentication(client):
    response = await client.get("/reports")
    assert response.status_code == 401


async def test_create_report_success(client, make_user, plant_id_factory):
    _admin, headers = await make_user(role="safety_officer")
    plant_id = await plant_id_factory()

    response = await client.post(
        "/reports",
        headers=headers,
        json={
            "report_type": "monthly_safety_summary",
            "plant_id": plant_id,
            "date_range_start": "2026-06-01",
            "date_range_end": "2026-06-30",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["file_url"] is None


async def test_create_report_invalid_date_range_returns_422(client, make_user, plant_id_factory):
    _admin, headers = await make_user(role="safety_officer")
    plant_id = await plant_id_factory()

    response = await client.post(
        "/reports", headers=headers,
        json={"report_type": "monthly_safety_summary", "plant_id": plant_id, "date_range_start": "2026-06-30", "date_range_end": "2026-06-01"},
    )
    assert response.status_code == 422


async def test_create_report_requires_write_role(client, make_user, plant_id_factory):
    _viewer, headers = await make_user(role="government_auditor")
    plant_id = await plant_id_factory()

    response = await client.post(
        "/reports", headers=headers,
        json={"report_type": "audit", "plant_id": plant_id, "date_range_start": "2026-06-01", "date_range_end": "2026-06-30"},
    )
    assert response.status_code == 403


async def test_complete_report_success(client, make_user, plant_id_factory):
    _admin, headers = await make_user(role="safety_officer")
    plant_id = await plant_id_factory()

    create_resp = await client.post(
        "/reports", headers=headers,
        json={"report_type": "monthly_safety_summary", "plant_id": plant_id, "date_range_start": "2026-06-01", "date_range_end": "2026-06-30"},
    )
    report_id = create_resp.json()["id"]

    complete_resp = await client.post(
        f"/reports/{report_id}/complete", headers=headers, json={"file_url": "s3://aegis-reports/monthly-2026-06.pdf"}
    )
    assert complete_resp.status_code == 200
    body = complete_resp.json()
    assert body["status"] == "completed"
    assert body["file_url"] == "s3://aegis-reports/monthly-2026-06.pdf"
    assert body["generated_at"] is not None


async def test_complete_already_completed_report_returns_422(client, make_user, plant_id_factory):
    _admin, headers = await make_user(role="safety_officer")
    plant_id = await plant_id_factory()

    create_resp = await client.post(
        "/reports", headers=headers,
        json={"report_type": "monthly_safety_summary", "plant_id": plant_id, "date_range_start": "2026-06-01", "date_range_end": "2026-06-30"},
    )
    report_id = create_resp.json()["id"]

    await client.post(f"/reports/{report_id}/complete", headers=headers, json={"file_url": "s3://x/1.pdf"})
    second = await client.post(f"/reports/{report_id}/complete", headers=headers, json={"file_url": "s3://x/2.pdf"})
    assert second.status_code == 422


async def test_get_report_not_found(client, make_user):
    _admin, headers = await make_user(role="safety_officer")
    response = await client.get("/reports/999999999", headers=headers)
    assert response.status_code == 404


async def test_filter_reports_by_type(client, make_user, plant_id_factory):
    _admin, headers = await make_user(role="safety_officer")
    plant_id = await plant_id_factory()

    await client.post("/reports", headers=headers, json={"report_type": "type_a", "plant_id": plant_id, "date_range_start": "2026-06-01", "date_range_end": "2026-06-30"})
    await client.post("/reports", headers=headers, json={"report_type": "type_b", "plant_id": plant_id, "date_range_start": "2026-06-01", "date_range_end": "2026-06-30"})

    response = await client.get("/reports?report_type=type_a", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(r["report_type"] == "type_a" for r in body["items"])
