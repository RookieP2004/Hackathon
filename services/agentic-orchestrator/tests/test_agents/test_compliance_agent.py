import asyncio

from app.agents.compliance_agent import ComplianceAgent

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"


async def test_flags_the_two_real_expired_but_active_permits(bus):
    # permits 1 and 2 are real seeded rows: status='active' but valid_to already in the
    # past (confirmed while building the Risk Fusion Engine pass) -- exactly the genuine
    # compliance-violation fact this agent's rule evaluation should catch.
    agent = ComplianceAgent(bus, POSTGRES_DSN)
    agent.agent_id = "zztest-compliance-agent"
    agent.memory.agent_id = "zztest-compliance-agent"

    assertions = []

    async def _listen():
        async for message in bus.subscribe("agent.assertion"):
            if message.agent_id == "zztest-compliance-agent" and message.payload.get("permit_id") is not None:
                assertions.append(message)
                if len(assertions) >= 2:
                    break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.1)
    await agent.tick()

    try:
        await asyncio.wait_for(listener, timeout=5.0)
    except asyncio.TimeoutError:
        listener.cancel()

    flagged_ids = {a.payload["permit_id"] for a in assertions}
    assert {1, 2}.issubset(flagged_ids)
    assert all(a.confidence == 1.0 for a in assertions)
