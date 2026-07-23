# incident-service

Incident lifecycle, open, acknowledge, escalate, close, per ARCHITECTURE.md section 19

Generated from `libs/service-template` via `scripts/new-service.sh`. See `ARCHITECTURE.md` §8.1 for this service's owned responsibilities and `DATABASE_SCHEMA.md` for the tables it owns migrations for.

**Local dev:** `cd services/incident-service && poetry install && poetry run uvicorn app.main:app --reload`
