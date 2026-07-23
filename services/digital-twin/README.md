# digital-twin

Live plant state graph, topology, and simulation layer, per ARCHITECTURE.md section 16

Generated from `libs/service-template` via `scripts/new-service.sh`. See `ARCHITECTURE.md` §8.1 for this service's owned responsibilities and `DATABASE_SCHEMA.md` for the tables it owns migrations for.

**Local dev:** `cd services/digital-twin && poetry install && poetry run uvicorn app.main:app --reload`
