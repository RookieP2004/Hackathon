# agentic-orchestrator

Playbook planning and execution, Emergency Agent, per ARCHITECTURE.md section 15 and AGENT_ARCHITECTURE.md section 9

Generated from `libs/service-template` via `scripts/new-service.sh`. See `ARCHITECTURE.md` §8.1 for this service's owned responsibilities and `DATABASE_SCHEMA.md` for the tables it owns migrations for.

**Local dev:** `cd services/agentic-orchestrator && poetry install && poetry run uvicorn app.main:app --reload`
