import asyncio

from app.agents.knowledge_agent import KnowledgeAgent
from app.agents import topics
from app.config import get_settings

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
RAG_SERVICE_URL = "http://localhost:8008"


async def test_knowledge_agent_answers_a_grounded_query(bus):
    settings = get_settings()
    agent = KnowledgeAgent(bus, POSTGRES_DSN, RAG_SERVICE_URL, settings.jwt_secret, settings.jwt_algorithm)
    agent.agent_id = "zztest-knowledge-agent"
    agent.memory.agent_id = "zztest-knowledge-agent"

    subscriber_task = asyncio.create_task(agent.run_subscriber_loop())
    await asyncio.sleep(0.2)
    try:
        response = await bus.request(
            requester_agent_id="zztest-requester", requester_version="v1",
            target_topic=topics.KNOWLEDGE_QUERY_REQUEST, response_topic="zztest-requester.response",
            payload={"query": "what is the inspection interval for fire suppression systems"}, timeout=20.0,
        )
    finally:
        subscriber_task.cancel()

    assert response is not None
    assert response.payload["refused"] is False
    assert len(response.payload["chunks"]) > 0


async def test_knowledge_agent_refuses_ungrounded_nonsense(bus):
    settings = get_settings()
    agent = KnowledgeAgent(bus, POSTGRES_DSN, RAG_SERVICE_URL, settings.jwt_secret, settings.jwt_algorithm)
    agent.agent_id = "zztest-knowledge-agent-2"
    agent.memory.agent_id = "zztest-knowledge-agent-2"

    subscriber_task = asyncio.create_task(agent.run_subscriber_loop())
    await asyncio.sleep(0.2)
    try:
        response = await bus.request(
            requester_agent_id="zztest-requester", requester_version="v1",
            target_topic=topics.KNOWLEDGE_QUERY_REQUEST, response_topic="zztest-requester.response",
            payload={"query": "xk7 qplj wobbledeglorp banana spaceship 9942"}, timeout=20.0,
        )
    finally:
        subscriber_task.cancel()

    assert response is not None
    assert response.payload["refused"] is True
