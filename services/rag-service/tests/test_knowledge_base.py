from __future__ import annotations


async def test_list_documents_requires_authentication(client):
    response = await client.get("/knowledge-base/documents")
    assert response.status_code == 401


async def test_create_document_success(client, make_user):
    _admin, headers = await make_user(role="safety_officer")
    response = await client.post(
        "/knowledge-base/documents",
        headers=headers,
        json={
            "title": "Confined Space Entry SOP",
            "document_class": "safety_sop",
            "content": "Before entry, verify atmospheric testing for oxygen, LEL, and toxic gases.",
            "section_reference": "SOP-CS-01",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["document_class"] == "safety_sop"
    assert body["authority"] == "internal"
    assert body["superseded_at"] is None


async def test_create_document_invalid_class_returns_422(client, make_user):
    _admin, headers = await make_user(role="safety_officer")
    response = await client.post(
        "/knowledge-base/documents", headers=headers,
        json={"title": "x", "document_class": "not_a_real_class", "content": "x"},
    )
    assert response.status_code == 422


async def test_create_document_requires_write_role(client, make_user):
    _viewer, headers = await make_user(role="viewer")
    response = await client.post(
        "/knowledge-base/documents", headers=headers,
        json={"title": "x", "document_class": "safety_sop", "content": "x"},
    )
    assert response.status_code == 403


async def test_get_document_not_found(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/knowledge-base/documents/999999999", headers=headers)
    assert response.status_code == 404


async def test_update_document_success(client, make_user):
    _admin, headers = await make_user(role="safety_officer")
    create_resp = await client.post(
        "/knowledge-base/documents", headers=headers,
        json={"title": "Hot Work Permit SOP", "document_class": "safety_sop", "content": "Original content"},
    )
    document_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/knowledge-base/documents/{document_id}", headers=headers, json={"content": "Updated content with fire watch requirement"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["content"] == "Updated content with fire watch requirement"


async def test_supersede_document_blocks_further_updates(client, make_user):
    _admin, headers = await make_user(role="safety_officer")
    create_resp = await client.post(
        "/knowledge-base/documents", headers=headers,
        json={"title": "Old SOP", "document_class": "safety_sop", "content": "x"},
    )
    document_id = create_resp.json()["id"]

    supersede_resp = await client.post(f"/knowledge-base/documents/{document_id}/supersede", headers=headers)
    assert supersede_resp.status_code == 200
    assert supersede_resp.json()["superseded_at"] is not None

    resupersede_resp = await client.post(f"/knowledge-base/documents/{document_id}/supersede", headers=headers)
    assert resupersede_resp.status_code == 422

    update_resp = await client.patch(f"/knowledge-base/documents/{document_id}", headers=headers, json={"content": "new"})
    assert update_resp.status_code == 422


async def test_search_documents_by_keyword(client, make_user):
    _admin, headers = await make_user(role="safety_officer")
    await client.post(
        "/knowledge-base/documents", headers=headers,
        json={"title": "Gas Detector Calibration", "document_class": "equipment_manual", "content": "Calibrate H2S sensors monthly using certified span gas."},
    )
    await client.post(
        "/knowledge-base/documents", headers=headers,
        json={"title": "Fire Extinguisher Inspection", "document_class": "maintenance_manual", "content": "Inspect fire extinguishers quarterly."},
    )

    response = await client.get("/knowledge-base/search?q=span gas", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Gas Detector Calibration"


async def test_search_excludes_superseded_documents(client, make_user):
    _admin, headers = await make_user(role="safety_officer")
    create_resp = await client.post(
        "/knowledge-base/documents", headers=headers,
        json={"title": "Legacy Lockout Tagout SOP", "document_class": "safety_sop", "content": "Legacy LOTO wording unique-marker-xyz"},
    )
    document_id = create_resp.json()["id"]
    await client.post(f"/knowledge-base/documents/{document_id}/supersede", headers=headers)

    response = await client.get("/knowledge-base/search?q=unique-marker-xyz", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_filter_documents_by_class_and_current_only(client, make_user):
    _admin, headers = await make_user(role="safety_officer")
    create_resp = await client.post(
        "/knowledge-base/documents", headers=headers,
        json={"title": "DGMS Circular 5", "document_class": "dgms", "content": "x"},
    )
    document_id = create_resp.json()["id"]
    await client.post(
        "/knowledge-base/documents", headers=headers,
        json={"title": "OISD Standard 105", "document_class": "oisd", "content": "y"},
    )

    response = await client.get("/knowledge-base/documents?document_class=dgms&current_only=true", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(d["document_class"] == "dgms" for d in body["items"])
    assert any(d["id"] == document_id for d in body["items"])

    await client.post(f"/knowledge-base/documents/{document_id}/supersede", headers=headers)
    response2 = await client.get("/knowledge-base/documents?document_class=dgms&current_only=true", headers=headers)
    assert all(d["id"] != document_id for d in response2.json()["items"])
