import asyncio

import asyncpg

from app.agents.prediction_agent import PredictionAgent
from app.agents.risk_fusion_agent import RiskFusionAgent

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"


async def _seed_risk_score(equipment_id: int, score: float, factors: list[dict]) -> int:
    import json

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        return await conn.fetchval(
            "INSERT INTO risk_scores (equipment_id, score, confidence, contributing_factors, model_version) "
            "VALUES ($1, $2, 0.85, $3::jsonb, 'risk-fusion:zztest_explosion:v1') RETURNING id",
            equipment_id, score, json.dumps(factors),
        )
    finally:
        await conn.close()


async def test_risk_fusion_agent_only_reports_multi_factor_correlations(bus):
    single_factor_id = await _seed_risk_score(2, 50.0, [{"evidence_node_id": "a", "source_type": "sensor", "likelihood_ratio": 3.0, "evidence_refs": []}])
    multi_factor_id = await _seed_risk_score(2, 70.0, [
        {"evidence_node_id": "a", "source_type": "sensor", "likelihood_ratio": 3.0, "evidence_refs": []},
        {"evidence_node_id": "b", "source_type": "sensor", "likelihood_ratio": 5.0, "evidence_refs": []},
    ])

    agent = RiskFusionAgent(bus, POSTGRES_DSN)
    agent.agent_id = "zztest-risk-fusion-agent"
    agent.memory.agent_id = "zztest-risk-fusion-agent"
    agent._last_seen_id = single_factor_id - 1

    assertions = []

    async def _listen():
        async for message in bus.subscribe("agent.assertion"):
            if message.agent_id == "zztest-risk-fusion-agent":
                assertions.append(message)
                break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.1)
    await agent.tick()
    await asyncio.wait_for(listener, timeout=5.0)

    assert len(assertions) == 1
    assert assertions[0].payload["contributing_factor_count"] == 2


async def test_prediction_agent_publishes_every_scored_row_with_severity(bus):
    risk_score_id = await _seed_risk_score(3, 82.0, [{"evidence_node_id": "a", "source_type": "sensor", "likelihood_ratio": 3.0, "evidence_refs": []}])

    agent = PredictionAgent(bus, POSTGRES_DSN)
    agent.agent_id = "zztest-prediction-agent"
    agent.memory.agent_id = "zztest-prediction-agent"
    agent._last_seen_id = risk_score_id - 1

    assertions = []

    async def _listen():
        async for message in bus.subscribe("agent.assertion"):
            if message.agent_id == "zztest-prediction-agent":
                assertions.append(message)
                break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.1)
    await agent.tick()
    await asyncio.wait_for(listener, timeout=5.0)

    assert len(assertions) == 1
    assert assertions[0].payload["severity"] == "critical"
    assert assertions[0].payload["score"] == 82.0
