# AEGIS AI — Autonomous Industrial Safety Operating System

Production-grade monorepo. Started as a clean scaffold (per `docs/DEVELOPMENT_ROADMAP.md`'s 170 milestones); the database layer, authentication, and 11 of the 15 backend services now carry real, empirically-verified business logic end to end — see "What's Actually Implemented" below.

## Design Documents

Every architectural decision behind this scaffold is documented in `docs/`, in build order:

1. `docs/ARCHITECTURE.md` — overall system architecture
2. `docs/UI_UX_SPECIFICATION.md` — every screen's design spec
3. `docs/DATABASE_SCHEMA.md` — PostgreSQL/TimescaleDB schema
4. `docs/AGENT_ARCHITECTURE.md` — the 12-agent fleet
5. `docs/RISK_FUSION_ENGINE.md` — the Bayesian reasoning engine
6. `docs/KNOWLEDGE_GRAPH.md` — the Neo4j ontology
7. `docs/RAG_SYSTEM.md` — the retrieval-augmented generation pipeline
8. `docs/DIGITAL_TWIN_EXPERIENCE.md` — the 3D visualization engine
9. `docs/DEVELOPMENT_ROADMAP.md` — the 170-milestone build plan this scaffold exists to serve

## One Deliberate Stack Deviation From `ARCHITECTURE.md` §8.2

That document originally proposed a Node/Go split for high-throughput I/O services alongside Python for AI-adjacent ones. This scaffold standardizes **every backend service on Python 3.12 + FastAPI**, per explicit direction — a real, considered change from the original design, not a silent drift. The trade-off this accepts: Python's async I/O throughput ceiling is lower than Go's for the highest-volume ingestion paths (`ingestion-gateway`, `realtime-gateway`) — acceptable at hackathon and early-commercial scale, revisit if `NFR-7`'s 500,000-sensor target is approached in practice.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript, TailwindCSS, shadcn/ui, Framer Motion, React Query, Zustand, Socket.IO Client, React Flow, Three.js, React Three Fiber |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2.x, Alembic, Pydantic v2, Redis, Celery, python-socketio, Kafka, MQTT |
| Databases | PostgreSQL 16 + TimescaleDB, Neo4j 5, Redis |
| AI | LangGraph, LangChain, OpenAI, Anthropic (Claude), Sentence Transformers |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

## Monorepo Layout

```
aegis-ai/
├── apps/
│   ├── web/                # Next.js 15 frontend — see UI_UX_SPECIFICATION.md
│   └── mobile/              # Reserved — not scaffolded in this pass (no mobile stack specified yet)
├── services/                 # 15 independently-deployable FastAPI services — see ARCHITECTURE.md §8
│   ├── ingestion-gateway/
│   ├── anomaly-detection/    # stub — see "What's Actually Implemented"
│   ├── computer-vision/
│   ├── predictive-risk-engine/
│   ├── digital-twin/
│   ├── knowledge-graph/
│   ├── rag-service/
│   ├── agentic-orchestrator/
│   ├── incident-service/
│   ├── notification-service/
│   ├── identity-rbac/
│   ├── audit-log/            # stub
│   ├── api-gateway/          # stub
│   ├── realtime-gateway/     # stub
│   └── iot-simulator/        # physics-informed sensor/scenario simulator behind the Digital Twin/Vision demo
├── libs/
│   ├── db/                    # The complete SQLAlchemy schema + one consolidated Alembic chain — see libs/db/README.md
│   ├── service-template/     # Canonical FastAPI service scaffold every service above is generated from
│   ├── schemas/               # Shared event/API schemas (Avro, JSON-Schema, OpenAPI) — source of truth across languages
│   ├── design-system/         # Shared React component library (wraps shadcn/ui per design tokens)
│   └── sim-data/              # Physics-informed sensor/incident simulator (ARCHITECTURE.md §17.4)
├── infra/
│   ├── docker-compose/        # Local dev environment — the only thing you need to run this repo locally
│   ├── kubernetes/            # Reserved for cloud deployment (ARCHITECTURE.md §24)
│   └── terraform/             # Reserved for cloud infrastructure-as-code
├── scripts/                    # Cross-cutting dev scripts (service generator, reseed, demo checks)
├── docs/                       # The nine design documents this scaffold implements
└── .github/workflows/          # CI
```

## Why Two Package Ecosystems, Not a Forced Single One

The frontend and `libs/design-system`/`libs/schemas` are a **pnpm + Turborepo workspace** (see `pnpm-workspace.yaml`, `turbo.json`). Every Python service under `services/` is **independently Poetry-packaged** with its own `pyproject.toml`/`poetry.lock` — there is no unified Python workspace tool imposing shared dependency versions across services. This is a deliberate choice, not a gap: `ARCHITECTURE.md` §8.3/`NFR-14` require services to be independently deployable and independently versionable, and a forced shared Python dependency tree is the single most common way monorepos quietly violate that requirement. The root `Makefile` bridges both ecosystems with one consistent command surface.

## Quickstart

```bash
cp .env.example .env                    # fill in secrets (LLM API keys, JWT secret)
make up                                  # starts every infra dependency + service via Docker Compose
make web                                 # runs the Next.js frontend in dev mode (outside Docker, for fast HMR)
make test                                # runs the full test suite across both ecosystems
```

See `Makefile` for the full command surface.

## What's Actually Implemented

Real, empirically-verified business logic (each built against live PostgreSQL/TimescaleDB/Neo4j/Redis instances and exercised end to end, not just reviewed) now spans the database layer, auth, and 11 of the 15 backend services:

- **The complete database** (`libs/db`) — every table from `DATABASE_SCHEMA.md` (34 relational/partitioned tables, 9 TimescaleDB hypertables, all triggers, constraints, compression/retention policies, continuous aggregates) plus `worker_location_history` (a considered addition, not in the original design — see that module's docstring for the privacy-by-design constraints it carries) and the `refresh_tokens`/`password_reset_tokens` pair supporting the auth system below. Seeded with a full demo plant (`libs/db/seed/`) reusing the exact equipment/sensor tags (`V-12`, `RV-9`, `GS-14`, `PT-22`) from `RISK_FUSION_ENGINE.md`'s worked example.
- **The complete authentication system** — JWT access tokens + rotation-on-use refresh tokens with theft-detection chain-revocation, RBAC (`identity-rbac`'s `require_roles()` dependency) covering the eight-role set (System Admin, Plant Admin, Safety Officer, Maintenance Engineer, Operator, Emergency Team, Government Auditor, Viewer), login/forgot-password/reset-password, and audit logging — backend (`services/identity-rbac`) and frontend (`apps/web`'s `(auth)` route group, Next.js Route Handlers holding the refresh token in an `httpOnly` cookie, middleware-gated protected routes).
- **`ingestion-gateway`** — sensor/reading ingestion with out-of-range and quality validation against each sensor's own configured range.
- **`predictive-risk-engine`** — the six-stage Risk Fusion Engine (`RISK_FUSION_ENGINE.md`): evidence normalization (with stuck/stale-sensor fault detection), temporal reasoning, knowledge-graph-anchored fusion, and live risk scoring against a running sensor simulator.
- **`knowledge-graph`** — the Neo4j ontology (`KNOWLEDGE_GRAPH.md`), schema application, sync endpoints, and a role-gated Cypher query surface with a hardened write/procedure-call blocklist.
- **`computer-vision`** — detection/event endpoints backed by real stored events, role-gated per `identity-rbac`'s role set.
- **`digital-twin`** — real Postgres+Neo4j-backed topology/state for the 3D visualization frontend consumes.
- **`rag-service`** — the RAG pipeline (`RAG_SYSTEM.md`): chunking, embeddings, hybrid (keyword + vector) search, cross-encoder re-ranking with graph-aware boosting, and a two-layer hallucination gate (low-confidence refusal checked against both the raw and graph-boosted relevance scores, plus cross-source numeric-conflict detection).
- **`agentic-orchestrator`** — the 12-agent fleet (`AGENT_ARCHITECTURE.md`): Supervisor, Emergency, Permit, Vision, Worker, Prediction agents and the rest, coordinated over a real message bus, with incident deduplication (an already-open incident suppresses duplicate automated responses on the same equipment), a fail-closed permit gate, and the enterprise report generator (PDF/Excel/CSV across all eleven report types).
- **`incident-service`** / **`notification-service`** — incident lifecycle, timeline, and multi-channel alert escalation against real stored data.
- **`iot-simulator`** — the physics-informed sensor/scenario simulator (world state, control/scenario endpoints) the Digital Twin and Vision demo flows drive against.

Four services remain genuine stubs — health check only, no business logic yet: **`anomaly-detection`**, **`api-gateway`**, **`audit-log`**, **`realtime-gateway`**. `docs/DEVELOPMENT_ROADMAP.md` M1-M170 is the build order for the rest.

### Real Bugs Found While Building This (Not Hypothetical)

Both of the above were verified by actually running them, not just written and reviewed — which surfaced genuine defects a review alone would have missed. The most consequential ones, in case they recur elsewhere:

- `__mapper_args__ = {"primary_key": [...]}` does **not** create an actual database primary key — every hypertable needed `primary_key=True` on both composite-key columns directly. Full list in `libs/db/README.md`.
- `passlib`'s bcrypt backend is broken against modern `bcrypt` (4.1+) — it probes a `bcrypt.__about__` module that no longer exists. Fixed by using `bcrypt` directly (`services/identity-rbac/app/core/security.py`), not by pinning around an unmaintained dependency.
- `next dev --turbopack` at Next.js 15.0.3 breaks the dev-mode error-page renderer, which then masks the real underlying error. The `dev` script deliberately does not pass `--turbopack` at this pinned version.
- Node's server-side `fetch()` can resolve `localhost` to the IPv6 loopback first; every service-to-service default URL in this repo uses `127.0.0.1` instead, specifically to avoid this.
