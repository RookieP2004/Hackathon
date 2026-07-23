# anomaly-detection

Per-signal statistical and ML anomaly models, Sensor Agent's Core, per AGENT_ARCHITECTURE.md section 1

Generated from `libs/service-template` via `scripts/new-service.sh`. See `ARCHITECTURE.md` §8.1 for this service's owned responsibilities and `DATABASE_SCHEMA.md` for the tables it owns migrations for.

**Local dev:** `cd services/anomaly-detection && poetry install && poetry run uvicorn app.main:app --reload`
