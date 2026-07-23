import asyncio

from app.agents.vision_agent import VisionAgent

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
COMPUTER_VISION_URL = "http://localhost:8004"


async def test_vision_agent_republishes_real_confirmed_events(bus):
    agent = VisionAgent(bus, POSTGRES_DSN, COMPUTER_VISION_URL, jwt_secret="changeme_generate_a_real_secret_before_any_shared_deployment", jwt_algorithm="HS256")
    agent.agent_id = "zztest-vision-agent"
    agent.memory.agent_id = "zztest-vision-agent"

    assertions = []

    async def _listen():
        async for message in bus.subscribe("agent.assertion"):
            if message.agent_id == "zztest-vision-agent":
                assertions.append(message)
                break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.1)
    await agent.tick()

    # A fresh agent's _last_seen_observed_at starts None, so its first tick treats every
    # currently-confirmed event as new -- computer-vision's live pipeline has been running
    # continuously since the Vision AI pass, so real historical events are always present.
    await asyncio.wait_for(listener, timeout=5.0)

    assert len(assertions) >= 1
    msg = assertions[0]
    assert msg.confidence is not None
    assert 0 <= msg.confidence <= 1
    assert "detection_class" in msg.payload
    assert msg.reasoning is not None and "computer-vision confirmed" in msg.reasoning
