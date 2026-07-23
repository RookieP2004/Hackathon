"""
Wires up and runs all twelve fleet agents together — AGENT_ARCHITECTURE.md's
complete agent roster, each running independently (its own asyncio task),
communicating over the real shared Agent Bus (Redis pub/sub), each
maintaining its own memory, confidence scoring, decision logging, and
failure-recovery policy per its own module.
"""

from __future__ import annotations

import asyncpg

from aegis_agents import BaseAgent, MessageBus, ensure_agent_memory_tables

from app.agents.compliance_agent import ComplianceAgent
from app.agents.emergency_agent import EmergencyAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.learning_agent import LearningAgent
from app.agents.maintenance_agent import MaintenanceAgent
from app.agents.permit_agent import PermitAgent
from app.agents.prediction_agent import PredictionAgent
from app.agents.risk_fusion_agent import RiskFusionAgent
from app.agents.sensor_agent import SensorAgent
from app.agents.supervisor_agent import SupervisorAgent
from app.agents.vision_agent import VisionAgent
from app.agents.worker_agent import WorkerAgent


class AgentFleet:
    def __init__(
        self, *, postgres_dsn: str, redis_url: str, knowledge_graph_url: str, computer_vision_url: str,
        rag_service_url: str, predictive_risk_engine_url: str, incident_service_url: str,
        notification_service_url: str, jwt_secret: str, jwt_algorithm: str, pg_pool: asyncpg.Pool | None = None,
    ) -> None:
        self.bus = MessageBus(redis_url)
        self._postgres_dsn = postgres_dsn
        self._pg_pool = pg_pool
        self._knowledge_graph_url = knowledge_graph_url
        self._computer_vision_url = computer_vision_url
        self._rag_service_url = rag_service_url
        self._predictive_risk_engine_url = predictive_risk_engine_url
        self._incident_service_url = incident_service_url
        self._notification_service_url = notification_service_url
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self.agents: list[BaseAgent] = []

    async def start(self) -> None:
        await ensure_agent_memory_tables(self._postgres_dsn)
        await self.bus.connect()

        self.agents = [
            SensorAgent(self.bus, self._postgres_dsn, self._pg_pool),
            VisionAgent(self.bus, self._postgres_dsn, self._computer_vision_url, jwt_secret=self._jwt_secret, jwt_algorithm=self._jwt_algorithm, pg_pool=self._pg_pool),
            WorkerAgent(self.bus, self._postgres_dsn, self._computer_vision_url, jwt_secret=self._jwt_secret, jwt_algorithm=self._jwt_algorithm, pg_pool=self._pg_pool),
            PermitAgent(self.bus, self._postgres_dsn, self._knowledge_graph_url, jwt_secret=self._jwt_secret, jwt_algorithm=self._jwt_algorithm, pg_pool=self._pg_pool),
            MaintenanceAgent(self.bus, self._postgres_dsn, self._pg_pool),
            KnowledgeAgent(self.bus, self._postgres_dsn, self._rag_service_url, self._jwt_secret, self._jwt_algorithm, pg_pool=self._pg_pool),
            RiskFusionAgent(self.bus, self._postgres_dsn, self._pg_pool),
            PredictionAgent(self.bus, self._postgres_dsn, self._pg_pool),
            EmergencyAgent(
                self.bus, self._postgres_dsn, predictive_risk_engine_url=self._predictive_risk_engine_url,
                incident_service_url=self._incident_service_url, notification_service_url=self._notification_service_url,
                rag_service_url=self._rag_service_url, jwt_secret=self._jwt_secret, jwt_algorithm=self._jwt_algorithm,
                pg_pool=self._pg_pool,
            ),
            ComplianceAgent(self.bus, self._postgres_dsn, self._pg_pool),
            LearningAgent(self.bus, self._postgres_dsn, self._pg_pool),
            SupervisorAgent(self.bus, self._postgres_dsn, self._pg_pool),
        ]
        for agent in self.agents:
            agent.start()

    async def stop(self) -> None:
        for agent in self.agents:
            await agent.stop()
        await self.bus.close()

    def status(self) -> list[dict]:
        return [
            {
                "agent_id": agent.agent_id, "healthy": agent.is_healthy, "degraded_reason": agent.degraded_reason,
                "failure_mode": agent.failure_mode, "ticks": agent._ticks,
            }
            for agent in self.agents
        ]
