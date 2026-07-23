from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger

router = APIRouter(tags=["telemetry"])
logger = get_logger("iot-simulator.ws")


@router.websocket("/ws/telemetry")
async def telemetry_stream(websocket: WebSocket) -> None:
    """
    Streams one JSON telemetry snapshot per tick (app/loop.py drives the
    actual cadence and calls manager.broadcast()). On connect, the client is
    immediately sent the current snapshot rather than waiting up to a full
    tick_interval_seconds for the next broadcast, so a dashboard never renders
    an empty first frame.
    """
    manager = websocket.app.state.manager
    engine = websocket.app.state.engine

    await manager.connect(websocket)
    try:
        await websocket.send_json(engine.snapshot())
        while True:
            # This connection is fed by the broadcast loop, not by anything the
            # client sends — we just need to notice a disconnect promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
