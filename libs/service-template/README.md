# Service Template

The canonical FastAPI service scaffold referenced by `ARCHITECTURE.md` §23.3. Every directory under `services/` is generated from this template via `scripts/new-service.sh` (or `make new-service NAME=...`), not hand-copied — that script is the single place the template's shape is defined, so a future change to the template (e.g., adding OpenTelemetry tracing) can be re-applied consistently.

**Contains:** app-factory FastAPI setup, structured JSON logging, Pydantic Settings base config, `/health` endpoint, Poetry packaging, a healthcheck-aware Dockerfile.

**Does not contain:** any business logic, any database models, any real dependency wiring beyond the settings shape. Each generated service adds its own `alembic/` migration chain, its own domain models, and its own extra dependencies on top of this base.
