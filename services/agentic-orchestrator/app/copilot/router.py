"""
The AI Copilot's conversational endpoint. No LLM is available in this
environment (confirmed while building the RAG pipeline earlier in this
project), so "conversational" here means: a real embedding-based intent
classifier picks which real backend query to run, real entity resolution
grounds it to a real equipment/hazard, and the handler composes an answer
entirely out of real, cited data -- never a generated sentence that isn't
traceable to a real system call.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.auth import auth
from app.copilot import handlers
from app.copilot.entities import resolve_equipment, resolve_hazard_class
from app.copilot.intents import classifier
from app.copilot.session import get_session_context, set_session_context
from app.orchestrator.clients import ServiceClients

router = APIRouter(prefix="/copilot", tags=["copilot"])

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team", "government_auditor", "viewer")

_UNKNOWN_INTENT_MESSAGE = (
    "I don't have a confident answer for that. Try asking things like: "
    "\"what is happening\", \"why is risk increasing on V-12\", \"show machine history for V-12\", "
    "\"predict failures\", \"show permit violations\", \"generate an inspection report for V-12\", "
    "\"find similar incidents for V-12\", or \"explain the gas leak response regulation\"."
)


class CopilotQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


@router.post("/query", summary="Ask the Copilot a question -- every answer is grounded in a real backend call, cited, never fabricated")
async def post_copilot_query(payload: CopilotQueryRequest, request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    settings = request.app.state.settings
    clients: ServiceClients = request.app.state.copilot_clients
    postgres_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    session_id = payload.session_id or str(uuid.uuid4())
    session_context = await get_session_context(settings.redis_url, session_id)

    intent, intent_confidence = classifier.classify(payload.query)

    equipment = await resolve_equipment(postgres_dsn, payload.query)
    hazard_class = resolve_hazard_class(payload.query)
    # Follow-up questions ("why is that increasing?") don't repeat the equipment/hazard --
    # fall back to what this session last talked about.
    if equipment is None and session_context.get("equipment"):
        equipment = session_context["equipment"]
    if hazard_class is None and session_context.get("hazard_class"):
        hazard_class = session_context["hazard_class"]

    if intent == "current_state":
        result = await handlers.handle_current_state(clients)
    elif intent == "why_risk_increasing":
        result = await handlers.handle_why_risk_increasing(clients, equipment, hazard_class)
    elif intent == "machine_history":
        result = await handlers.handle_machine_history(clients, postgres_dsn, equipment)
    elif intent == "predict_failures":
        result = await handlers.handle_predict_failures(clients, equipment)
    elif intent == "permit_violations":
        result = await handlers.handle_permit_violations(postgres_dsn)
    elif intent == "generate_inspection_report":
        result = await handlers.handle_generate_inspection_report(clients, postgres_dsn, equipment)
    elif intent == "similar_incidents":
        result = await handlers.handle_similar_incidents(clients, equipment)
    elif intent == "explain_regulation":
        result = await handlers.handle_explain_regulation(clients, payload.query)
    else:
        result = {"answer": _UNKNOWN_INTENT_MESSAGE, "citations": [], "data": {}}

    await set_session_context(
        settings.redis_url, session_id,
        {"equipment": equipment, "hazard_class": hazard_class},
    )

    return {
        "session_id": session_id,
        "intent": intent,
        "intent_confidence": round(intent_confidence, 3),
        "answer": result["answer"],
        "citations": result["citations"],
        "entities": {"equipment": equipment, "hazard_class": hazard_class},
    }
