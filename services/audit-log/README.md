# audit-log

Immutable event and action history plus compliance export, per ARCHITECTURE.md section 19.5 and DATABASE_SCHEMA.md section 16

Generated from `libs/service-template` via `scripts/new-service.sh`. See `ARCHITECTURE.md` §8.1 for this service's owned responsibilities and `DATABASE_SCHEMA.md` for the tables it owns migrations for.

**Local dev:** `cd services/audit-log && poetry install && poetry run uvicorn app.main:app --reload`
