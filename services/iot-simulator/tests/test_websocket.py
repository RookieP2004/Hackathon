from __future__ import annotations

SENSOR_KIND_VALUES = {
    "temperature_c", "humidity_pct", "gas_pct_lel", "smoke_pct_obscuration", "noise_db",
}


def test_websocket_sends_initial_snapshot_immediately(client):
    with client.websocket_connect("/ws/telemetry") as ws:
        message = ws.receive_json()
        assert message["type"] == "telemetry"
        assert message["tick"] >= 0
        assert len(message["zones"]) == 5
        assert len(message["workers"]) == 4


def test_websocket_snapshot_contains_every_ambient_sensor_kind(client):
    with client.websocket_connect("/ws/telemetry") as ws:
        message = ws.receive_json()
    zone = message["zones"][0]
    assert set(zone["ambient"].keys()) == SENSOR_KIND_VALUES
    assert "camera" in zone
    assert {"event_type", "confidence", "person_count", "camera_id"} <= set(zone["camera"].keys())


def test_websocket_snapshot_contains_worker_vitals_and_gps(client):
    with client.websocket_connect("/ws/telemetry") as ws:
        message = ws.receive_json()
    worker = message["workers"][0]
    assert set(worker["vitals"].keys()) == {"heart_rate_bpm", "stress_index", "body_temperature_c"}
    assert "lat" in worker["gps"] and "lon" in worker["gps"]


def test_websocket_streams_a_new_tick_every_interval(client):
    with client.websocket_connect("/ws/telemetry") as ws:
        first = ws.receive_json()
        second = ws.receive_json()
    assert second["tick"] == first["tick"] + 1
    assert second["timestamp"] > first["timestamp"]


def test_multiple_clients_receive_the_same_broadcast(client, app):
    with client.websocket_connect("/ws/telemetry") as ws_a, client.websocket_connect("/ws/telemetry") as ws_b:
        # each connection gets its own immediate snapshot on connect...
        ws_a.receive_json()
        ws_b.receive_json()
        # ...then both must observe the same subsequent broadcast tick.
        next_a = ws_a.receive_json()
        next_b = ws_b.receive_json()
    assert next_a["tick"] == next_b["tick"]


def test_disconnect_is_tracked_by_connection_manager(client, app):
    with client.websocket_connect("/ws/telemetry") as ws:
        ws.receive_json()
        assert app.state.manager.connection_count == 1
    assert app.state.manager.connection_count == 0
