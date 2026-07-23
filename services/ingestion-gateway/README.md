# ingestion-gateway

Protocol adapters (MQTT, OPC-UA, Modbus) plus telemetry normalization, per ARCHITECTURE.md section 17.2

Generated from `libs/service-template` via `scripts/new-service.sh`. See `ARCHITECTURE.md` §8.1 for this service's owned responsibilities and `DATABASE_SCHEMA.md` for the tables it owns migrations for.

**Local dev:** `cd services/ingestion-gateway && poetry install && poetry run uvicorn app.main:app --reload`
