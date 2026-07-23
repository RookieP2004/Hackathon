# predictive-risk-engine

Cross-signal correlation, Bayesian risk fusion, survival scoring, per RISK_FUSION_ENGINE.md and AGENT_ARCHITECTURE.md sections 7, 8, 11

Generated from `libs/service-template` via `scripts/new-service.sh`. See `ARCHITECTURE.md` §8.1 for this service's owned responsibilities and `DATABASE_SCHEMA.md` for the tables it owns migrations for.

**Local dev:** `cd services/predictive-risk-engine && poetry install && poetry run uvicorn app.main:app --reload`
