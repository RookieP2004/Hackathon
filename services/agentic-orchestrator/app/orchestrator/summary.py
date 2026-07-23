"""
Generate AI Summary — assembled from two genuinely real sources: the actual
Risk Fusion Engine assessment that triggered this incident (real contributing
factors, real counterfactual, real recommendations) and rag-service's real,
citation-grounded retrieval of the relevant SOP/regulation for this hazard
class. No LLM API key is configured anywhere in this environment (confirmed
while building the RAG pipeline), so this is deliberately template-assembled
from those two real sources rather than free-text generation -- every
sentence is either a direct restatement of a real number/factor already
computed elsewhere, or a real citation rag-service actually retrieved, never
an invented claim. This is honest "AI Summary" within what this environment
can actually deliver, not a fabricated call to a model that isn't there.
"""

from __future__ import annotations

from app.orchestrator.clients import ServiceClients

_HAZARD_QUERY_TEMPLATES = {
    "explosion": "what is required for explosion prevention and gas concentration limits",
    "fire": "what is required for fire prevention and suppression response",
    "gas_leak": "what is the required response to a gas leak",
    "machine_failure": "what is the required maintenance response to equipment failure",
    "worker_injury": "what is the required response to a worker injury or PPE violation",
}


async def generate_ai_summary(clients: ServiceClients, *, hazard_class: str, equipment_tag: str, score: float, confidence: float, top_contributing_factors: list[dict], counterfactual: dict | None) -> dict:
    query = _HAZARD_QUERY_TEMPLATES.get(hazard_class, f"what is the required response to {hazard_class}")
    try:
        rag_result = await clients.query_knowledge(query)
    except Exception:
        rag_result = {"refused": True, "chunks": []}

    factor_lines = [
        f"- {f['source_type']}:{f['evidence_node_id']} (likelihood ratio {f['likelihood_ratio']:.1f})"
        for f in top_contributing_factors[:3]
    ]
    counterfactual_line = ""
    if counterfactual:
        counterfactual_line = (
            f"\nCounterfactual: removing '{counterfactual['removed_node_id']}' from the evidence would change the "
            f"posterior to {counterfactual['resulting_probability']:.1%} (from the current assessed probability)."
        )

    citation_lines = []
    if not rag_result.get("refused") and rag_result.get("chunks"):
        for chunk in rag_result["chunks"][:3]:
            citation_lines.append(f"- {chunk['citation']}")

    summary = (
        f"Automated risk assessment flagged a {hazard_class.replace('_', ' ')} risk on {equipment_tag} at a score of "
        f"{score:.1f}/100 (confidence {confidence:.0%}). This assessment was produced by the versioned Bayesian Risk "
        f"Fusion Engine, not this summary generator -- the summary only narrates what was already computed.\n\n"
        f"Top contributing evidence:\n" + "\n".join(factor_lines) + counterfactual_line
        + ("\n\nRelevant governing procedure/regulation (retrieved, cited):\n" + "\n".join(citation_lines) if citation_lines else
           "\n\nNo governing procedure/regulation could be retrieved above the minimum confidence threshold for this hazard class.")
    )

    return {
        "summary": summary,
        "citations": [c["citation"] for c in rag_result.get("chunks", [])[:3]] if not rag_result.get("refused") else [],
        "grounding": "risk_fusion_engine+rag_service" if citation_lines else "risk_fusion_engine_only",
    }
