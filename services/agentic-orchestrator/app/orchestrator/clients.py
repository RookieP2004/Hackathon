"""
Real HTTP clients to the three already-built services the Emergency Response
Orchestrator drives: incident-service (Generate Incident, Generate Timeline),
notification-service (Notify Users, Notify Emergency Team), and rag-service
(the retrieval-grounded material behind Generate AI Summary / Create
Regulatory Report). All three require a real signed JWT -- minted here the
same way computer-vision's/knowledge_agent's downstream integrations already
do, against the same shared secret and a real seeded user id.
"""

from __future__ import annotations

import asyncpg
import httpx

from aegis_api_common import ServiceActorTokenMinter


class ServiceClients:
    def __init__(
        self, *, postgres_dsn: str, incident_service_url: str, notification_service_url: str,
        rag_service_url: str, jwt_secret: str, jwt_algorithm: str,
        predictive_risk_engine_url: str | None = None, knowledge_graph_url: str | None = None,
    ) -> None:
        self._postgres_dsn = postgres_dsn
        self.incident_service_url = incident_service_url
        self.notification_service_url = notification_service_url
        self.rag_service_url = rag_service_url
        # Optional: only the Copilot's read-only cross-service queries need these two --
        # the Emergency Response Orchestrator flow never constructs a client with them set.
        self.predictive_risk_engine_url = predictive_risk_engine_url
        self.knowledge_graph_url = knowledge_graph_url
        # No direct DB access of its own left (see ServiceActorTokenMinter) -- no pool needed here.
        self._token_minter = ServiceActorTokenMinter(postgres_dsn=postgres_dsn, jwt_secret=jwt_secret, jwt_algorithm=jwt_algorithm)

    async def auth_headers(self) -> dict:
        """Public: other services this orchestrator talks to (e.g.
        predictive-risk-engine's `/fusion/assess`) share the same signing
        secret, so this same minted token authenticates against any of them."""
        return await self._token_minter.auth_headers()

    # ---- incident-service ----

    async def create_incident(self, *, incident_number: str, plant_id: int, zone_id: int | None, equipment_id: int | None, severity: str) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.incident_service_url}/incidents", headers=await self.auth_headers(),
                json={"incident_number": incident_number, "plant_id": plant_id, "zone_id": zone_id, "equipment_id": equipment_id, "severity": severity},
            )
            response.raise_for_status()
            return response.json()

    async def update_incident_summary(self, incident_id: int, summary: str) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{self.incident_service_url}/incidents/{incident_id}", headers=await self.auth_headers(),
                json={"ai_generated_summary": summary},
            )
            response.raise_for_status()
            return response.json()

    async def add_timeline_event(self, incident_id: int, *, event_type: str, event_data: dict, actor_type: str = "agent") -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.incident_service_url}/incidents/{incident_id}/timeline", headers=await self.auth_headers(),
                json={"event_type": event_type, "event_data": event_data, "actor_type": actor_type},
            )
            response.raise_for_status()
            return response.json()

    async def create_report(
        self, *, report_type: str, plant_id: int | None, parameters: dict,
        date_range_start=None, date_range_end=None,
    ) -> dict:
        import datetime

        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        start = date_range_start.isoformat() if date_range_start else today
        end = date_range_end.isoformat() if date_range_end else today
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.incident_service_url}/reports", headers=await self.auth_headers(),
                json={"report_type": report_type, "plant_id": plant_id, "date_range_start": start, "date_range_end": end, "parameters": parameters},
            )
            response.raise_for_status()
            return response.json()

    async def complete_report(self, report_id: int, *, file_url: str) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.incident_service_url}/reports/{report_id}/complete", headers=await self.auth_headers(), json={"file_url": file_url},
            )
            response.raise_for_status()
            return response.json()

    async def list_incidents(self, *, status: str | None = None, equipment_id: int | None = None, page_size: int = 50) -> list[dict]:
        params = {"page_size": page_size, "sort": "-opened_at"}
        if status:
            params["status"] = status
        if equipment_id is not None:
            params["equipment_id"] = equipment_id
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.incident_service_url}/incidents", headers=await self.auth_headers(), params=params)
            response.raise_for_status()
            return response.json()["items"]

    # ---- notification-service ----

    async def raise_alert(self, *, alert_type: str, severity: str, message: str, zone_id: int | None, equipment_id: int | None, related_incident_id: int | None) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.notification_service_url}/alerts", headers=await self.auth_headers(),
                json={
                    "alert_type": alert_type, "severity": severity, "message": message,
                    "zone_id": zone_id, "equipment_id": equipment_id, "sensor_id": None,
                    "related_incident_id": related_incident_id,
                },
            )
            response.raise_for_status()
            return response.json()

    async def list_alerts(self, *, status: str | None = None, equipment_id: int | None = None, page_size: int = 50) -> list[dict]:
        params = {"page_size": page_size, "sort": "-triggered_at"}
        if status:
            params["status"] = status
        if equipment_id is not None:
            params["equipment_id"] = equipment_id
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.notification_service_url}/alerts", headers=await self.auth_headers(), params=params)
            response.raise_for_status()
            return response.json()["items"]

    # ---- predictive-risk-engine ----

    async def assess_equipment(self, equipment_id: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{self.predictive_risk_engine_url}/fusion/assess/{equipment_id}", headers=await self.auth_headers())
            response.raise_for_status()
            return response.json()["assessments"]

    async def list_risk_scores(self, *, equipment_id: int | None = None, computed_at_gte: str | None = None, page_size: int = 50) -> list[dict]:
        params = {"page_size": page_size, "sort": "-computed_at"}
        if equipment_id is not None:
            params["equipment_id"] = equipment_id
        if computed_at_gte:
            params["computed_at_gte"] = computed_at_gte
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.predictive_risk_engine_url}/risk-engine/risk-scores", headers=await self.auth_headers(), params=params)
            response.raise_for_status()
            return response.json()["items"]

    async def list_predictions(self, *, equipment_id: int | None = None, page_size: int = 20) -> list[dict]:
        params = {"page_size": page_size, "sort": "-predicted_at"}
        if equipment_id is not None:
            params["equipment_id"] = equipment_id
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.predictive_risk_engine_url}/risk-engine/predictions", headers=await self.auth_headers(), params=params)
            response.raise_for_status()
            return response.json()["items"]

    async def list_maintenance(self, *, equipment_id: int | None = None, page_size: int = 20) -> list[dict]:
        params = {"page_size": page_size, "sort": "-created_at"}
        if equipment_id is not None:
            params["equipment_id"] = equipment_id
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.predictive_risk_engine_url}/maintenance", headers=await self.auth_headers(), params=params)
            response.raise_for_status()
            return response.json()["items"]

    # ---- knowledge-graph ----

    async def graph_similar_incidents(self, equipment_id: int, *, limit: int = 5) -> list[dict]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.knowledge_graph_url}/graph/equipment/{equipment_id}/similar-incidents",
                headers=await self.auth_headers(), params={"limit": limit},
            )
            response.raise_for_status()
            return response.json()["incidents"]

    async def graph_compliance_gaps(self, regulation_code: str, *, required_interval_days: int = 180) -> list[dict]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.knowledge_graph_url}/graph/regulations/{regulation_code}/compliance-gaps",
                headers=await self.auth_headers(), params={"required_interval_days": required_interval_days},
            )
            response.raise_for_status()
            return response.json()["gaps"]

    async def graph_worker_exposure(self, *, min_score: float = 70, within_minutes: int = 1440) -> list[dict]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.knowledge_graph_url}/graph/zones/worker-exposure",
                headers=await self.auth_headers(), params={"min_score": min_score, "within_minutes": within_minutes},
            )
            response.raise_for_status()
            return response.json()["exposed_workers"]

    # ---- rag-service ----

    async def query_knowledge(self, query: str) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.rag_service_url}/rag/query", headers=await self.auth_headers(), json={"query": query},
            )
            response.raise_for_status()
            return response.json()
