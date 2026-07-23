from __future__ import annotations

import os

# Must be set before app.main is first imported anywhere (module-level
# `settings = get_settings()` runs at import time) -- a fast tick keeps the
# WebSocket integration tests from needing multi-second real-time sleeps.
os.environ.setdefault("TICK_INTERVAL_SECONDS", "0.05")
os.environ.setdefault("SIMULATION_SEED", "123")

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c
