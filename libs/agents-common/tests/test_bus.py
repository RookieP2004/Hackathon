import asyncio

import pytest

from aegis_agents.bus import MessageBus
from aegis_agents.envelope import AgentMessage, MessageType

REDIS_URL = "redis://localhost:6379/0"


@pytest.fixture
async def bus():
    b = MessageBus(REDIS_URL)
    await b.connect()
    yield b
    await b.close()


async def test_publish_subscribe_round_trip(bus):
    received = []

    async def _listen():
        async for message in bus.subscribe("test.pubsub.roundtrip"):
            received.append(message)
            break

    listener_task = asyncio.create_task(_listen())
    await asyncio.sleep(0.2)  # let the subscription actually register with Redis before publishing

    sent = AgentMessage(agent_id="test-agent", agent_version="v1", message_type=MessageType.ASSERTION, payload={"x": 1})
    await bus.publish("test.pubsub.roundtrip", sent)

    await asyncio.wait_for(listener_task, timeout=3.0)
    assert len(received) == 1
    assert received[0].agent_id == "test-agent"
    assert received[0].payload == {"x": 1}


async def test_request_response_round_trip(bus):
    async def _responder():
        async for message in bus.subscribe("test.request.topic"):
            await bus.publish(
                "requester.response",
                AgentMessage(
                    agent_id="responder", agent_version="v1", message_type=MessageType.RESPONSE,
                    payload={"answer": 42}, correlation_id=message.correlation_id,
                ),
            )
            break

    responder_task = asyncio.create_task(_responder())
    await asyncio.sleep(0.2)

    response = await bus.request(
        requester_agent_id="requester", requester_version="v1", target_topic="test.request.topic",
        response_topic="requester.response", payload={"question": "?"}, timeout=3.0,
    )
    await responder_task

    assert response is not None
    assert response.payload == {"answer": 42}


async def test_request_times_out_when_nobody_responds(bus):
    response = await bus.request(
        requester_agent_id="requester", requester_version="v1", target_topic="test.nobody.listening",
        response_topic="requester.response.timeout", payload={}, timeout=1.0,
    )
    assert response is None
