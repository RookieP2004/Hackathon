from __future__ import annotations

import pytest


async def test_list_users_requires_authentication(client):
    response = await client.get("/users")
    assert response.status_code == 401


async def test_list_users_requires_admin_role(client, make_user):
    _user, headers = await make_user(role="operator")
    response = await client.get("/users", headers=headers)
    assert response.status_code == 403
    assert "system_admin" in response.json()["error"]["message"]


async def test_list_users_success_as_system_admin(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/users", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["total"] >= 1  # at least the admin we just created
    assert any(u["email"] == _admin.email for u in body["items"])


async def test_list_users_pagination(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    for _ in range(3):
        await make_user(role="viewer")

    response = await client.get("/users?page=1&page_size=2", headers=headers)
    body = response.json()
    assert response.status_code == 200
    assert len(body["items"]) == 2
    assert body["page_size"] == 2
    assert body["total"] >= 4


async def test_create_user_success(client, make_user):
    _admin, headers = await make_user(role="plant_admin")
    _viewer_role, _ = await make_user(role="viewer")  # ensures the role_ids fixture ran

    response = await client.post(
        "/users",
        headers=headers,
        json={"email": "new.operator@aegis-test.example", "full_name": "New Operator", "default_role_id": _admin.default_role_id},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.operator@aegis-test.example"
    assert body["status"] == "active"


async def test_create_user_duplicate_email_conflicts(client, make_user):
    admin, headers = await make_user(role="system_admin")
    response = await client.post(
        "/users",
        headers=headers,
        json={"email": admin.email, "full_name": "Duplicate", "default_role_id": admin.default_role_id},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_create_user_invalid_email_returns_422(client, make_user):
    admin, headers = await make_user(role="system_admin")
    response = await client.post(
        "/users",
        headers=headers,
        json={"email": "not-an-email", "full_name": "X", "default_role_id": admin.default_role_id},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_get_user_not_found(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/users/999999999", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_get_user_success(client, make_user):
    admin, headers = await make_user(role="system_admin")
    response = await client.get(f"/users/{admin.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == admin.id


async def test_update_user_success(client, make_user):
    admin, headers = await make_user(role="system_admin")
    target, _ = await make_user(role="viewer")

    response = await client.patch(f"/users/{target.id}", headers=headers, json={"full_name": "Renamed"})
    assert response.status_code == 200
    assert response.json()["full_name"] == "Renamed"


async def test_deactivate_user_requires_system_admin_not_plant_admin(client, make_user):
    _plant_admin, headers = await make_user(role="plant_admin")
    target, _ = await make_user(role="viewer")

    response = await client.delete(f"/users/{target.id}", headers=headers)
    assert response.status_code == 403


async def test_deactivate_user_success_as_system_admin(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    target, _ = await make_user(role="viewer")

    response = await client.delete(f"/users/{target.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "deactivated"


async def test_list_users_invalid_sort_field_returns_400(client, make_user):
    _admin, headers = await make_user(role="system_admin")
    response = await client.get("/users?sort=password_hash", headers=headers)
    assert response.status_code == 400
