# notification-service

Multi-channel escalation delivery, per ARCHITECTURE.md section 11.3

Generated from `libs/service-template` via `scripts/new-service.sh`. See `ARCHITECTURE.md` §8.1 for this service's owned responsibilities and `DATABASE_SCHEMA.md` for the tables it owns migrations for.

**Local dev:** `cd services/notification-service && poetry install && poetry run uvicorn app.main:app --reload`
