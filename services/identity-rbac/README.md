# identity-rbac

Users, roles, permissions, and sessions, per ARCHITECTURE.md sections 20 and 21

Generated from `libs/service-template` via `scripts/new-service.sh`. See `ARCHITECTURE.md` §8.1 for this service's owned responsibilities and `DATABASE_SCHEMA.md` for the tables it owns migrations for.

**Local dev:** `cd services/identity-rbac && poetry install && poetry run uvicorn app.main:app --reload`
