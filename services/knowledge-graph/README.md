# knowledge-graph

Neo4j-backed equipment, incident, and procedure graph, per KNOWLEDGE_GRAPH.md

Generated from `libs/service-template` via `scripts/new-service.sh`. See `ARCHITECTURE.md` §8.1 for this service's owned responsibilities and `DATABASE_SCHEMA.md` for the tables it owns migrations for.

**Local dev:** `cd services/knowledge-graph && poetry install && poetry run uvicorn app.main:app --reload`
