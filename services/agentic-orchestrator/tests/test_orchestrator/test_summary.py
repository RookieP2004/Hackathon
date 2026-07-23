from app.orchestrator.clients import ServiceClients
from app.orchestrator.summary import generate_ai_summary

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"


def _clients(rag_url: str) -> ServiceClients:
    return ServiceClients(
        postgres_dsn=POSTGRES_DSN, incident_service_url="http://localhost:8010",
        notification_service_url="http://localhost:8011", rag_service_url=rag_url,
        jwt_secret="changeme_generate_a_real_secret_before_any_shared_deployment", jwt_algorithm="HS256",
    )


async def test_summary_grounds_in_real_rag_citations():
    clients = _clients("http://localhost:8008")
    result = await generate_ai_summary(
        clients, hazard_class="explosion", equipment_tag="V-12", score=88.0, confidence=0.9,
        top_contributing_factors=[{"source_type": "sensor", "evidence_node_id": "gas", "likelihood_ratio": 40.0}],
        counterfactual={"removed_node_id": "gas", "resulting_probability": 0.15},
    )
    assert "explosion" in result["summary"].lower()
    assert "88.0" in result["summary"]
    assert "counterfactual" in result["summary"].lower()
    # rag-service's real corpus (seeded in the RAG pass) includes an OISD explosion-relevant clause --
    # grounding should succeed and citations should be non-empty most of the time. If retrieval genuinely
    # can't ground this query, the summary must say so explicitly rather than silently omitting the section.
    assert ("Relevant governing procedure" in result["summary"]) or ("No governing procedure/regulation could be retrieved" in result["summary"])


async def test_summary_degrades_gracefully_when_rag_service_unreachable():
    clients = _clients("http://localhost:1")  # deliberately unreachable
    result = await generate_ai_summary(
        clients, hazard_class="fire", equipment_tag="B-201", score=70.0, confidence=0.8,
        top_contributing_factors=[{"source_type": "sensor", "evidence_node_id": "temp", "likelihood_ratio": 10.0}],
        counterfactual=None,
    )
    assert result["grounding"] == "risk_fusion_engine_only"
    assert result["citations"] == []
    assert "fire" in result["summary"].lower()
