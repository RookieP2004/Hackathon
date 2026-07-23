from __future__ import annotations


async def test_list_weather_requires_authentication(client):
    response = await client.get("/weather")
    assert response.status_code == 401


async def test_ingest_weather_observation_success(client, make_user, plant_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    plant_id = await plant_id_factory()

    response = await client.post(
        "/weather",
        headers=headers,
        json={
            "plant_id": plant_id,
            "temperature_c": 34.5,
            "humidity_pct": 62.0,
            "wind_speed_ms": 3.2,
            "wind_direction_deg": 180,
            "conditions": "clear",
            "source": "imd_api",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["plant_id"] == plant_id
    assert body["temperature_c"] == 34.5


async def test_ingest_weather_observation_requires_write_role(client, make_user, plant_id_factory):
    _viewer, headers = await make_user(role="operator")
    plant_id = await plant_id_factory()

    response = await client.post(
        "/weather", headers=headers,
        json={"plant_id": plant_id, "source": "imd_api"},
    )
    assert response.status_code == 403


async def test_ingest_weather_invalid_wind_direction_returns_422(client, make_user, plant_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    plant_id = await plant_id_factory()

    response = await client.post(
        "/weather", headers=headers,
        json={"plant_id": plant_id, "source": "imd_api", "wind_direction_deg": 999},
    )
    assert response.status_code == 422


async def test_list_and_filter_weather_by_plant(client, make_user, plant_id_factory):
    _admin, headers = await make_user(role="plant_admin")
    plant_a = await plant_id_factory()
    plant_b = await plant_id_factory()

    await client.post("/weather", headers=headers, json={"plant_id": plant_a, "source": "imd_api"})
    await client.post("/weather", headers=headers, json={"plant_id": plant_b, "source": "imd_api"})

    response = await client.get(f"/weather?plant_id={plant_a}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(o["plant_id"] == plant_a for o in body["items"])
    assert len(body["items"]) == 1
