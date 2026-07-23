"""Agent Bus topic names — AGENT_ARCHITECTURE.md §0.3's four standard topics,
plus the dedicated request/response topic pairs the two synchronous-style
agents (Permit Agent, Knowledge Agent) listen on."""

ASSERTION = "agent.assertion"
ESCALATION = "agent.escalation"
HEALTH = "agent.health"

PERMIT_CONFLICT_CHECK_REQUEST = "permit.conflict_check.request"
PERMIT_CONFLICT_CHECK_RESPONSE = "permit.conflict_check.response"

KNOWLEDGE_QUERY_REQUEST = "knowledge.query.request"
KNOWLEDGE_QUERY_RESPONSE = "knowledge.query.response"
