# AEGIS AI — Development Roadmap
### 170 Independently Testable Milestones, Ordered for a Real Build

**Classification:** Internal — Engineering
**Document Owner:** Lead Software Engineer
**Version:** 1.0
**Source Documents:** `ARCHITECTURE.md`, `DATABASE_SCHEMA.md`, `AGENT_ARCHITECTURE.md`, `RISK_FUSION_ENGINE.md`, `KNOWLEDGE_GRAPH.md`, `RAG_SYSTEM.md`, `DIGITAL_TWIN_EXPERIENCE.md`, `UI_UX_SPECIFICATION.md` — every milestone below implements a specific, named artifact from one of these; none are generic placeholder tickets.

---

## 0. How to Read This Roadmap

### 0.1 Sizing Philosophy
Every milestone is scoped so one engineer can go from a clean starting point to a demonstrably working, tested increment in **1-3 hours**. This means milestones are deliberately narrower than a "feature" — "create the `plants` table" and "create the `zones` table" are separate milestones, not one "set up the database" milestone, because the latter isn't independently testable at a useful grain and can silently hide half-finished work.

### 0.2 Milestone Template
Every entry below follows the same eight-field structure the user specified, kept compact by design (this is a working roadmap, not a design rationale document — the *why* for each architectural choice already lives in the eight source documents; this document is the *what, in what order, proven how*):

- **Objective** — the one thing this milestone accomplishes
- **Files** — the actual files touched, using the folder structure `ARCHITECTURE.md` §23.2 already established
- **Tests** — the specific test(s) that must exist and pass
- **Expected Output** — what a reviewer sees when it's done (a command's output, a screen, a query result)
- **Acceptance Criteria** — the checklist that makes "done" objective, not a feeling
- **Dependencies** — which earlier milestone(s) must be complete first
- **Risk** — Low/Medium/High, with the one-clause reason
- **Estimated Time** — a number, not a range, forcing a real estimate

### 0.3 Numbering and Phases
Milestones are numbered M1-M170 in build order across 14 phases. The phase order is the dependency order a real team would actually need: you cannot build the Risk Fusion Agent (Phase 7) before the database tables it reads and writes exist (Phase 1), and you cannot wire the Digital Twin's Live Telemetry Binding Layer (Phase 10) before the Realtime Gateway it binds to exists (Phase 2). Within a phase, milestones are listed in the order they should be built, but many are parallelizable across engineers once their stated dependencies are satisfied — the Dependencies field is what actually governs sequencing, not position in the list.

### 0.4 Definition of Done
A milestone is not "done" because the code compiles. It is done when: the stated Tests exist and pass in CI, the Expected Output has been manually verified once by the implementing engineer, and every Acceptance Criterion is checked off. Milestones are never marked done "pending a later cleanup pass" — if a milestone needs a follow-up, that follow-up is itself a new, separately-tracked milestone.

### 0.5 Phase Overview

| Phase | Milestones | Covers |
|---|---|---|
| 0 | M1-M8 | Foundations & tooling |
| 1 | M9-M44 | Database layer (`DATABASE_SCHEMA.md`) |
| 2 | M45-M54 | Core backend service skeletons |
| 3 | M55-M58 | Event backbone |
| 4 | M59-M64 | Sensor simulator & ingestion |
| 5 | M65-M74 | Knowledge Graph (`KNOWLEDGE_GRAPH.md`) |
| 6 | M75-M86 | RAG system (`RAG_SYSTEM.md`) |
| 7 | M87-M110 | Agent fleet (`AGENT_ARCHITECTURE.md`, `RISK_FUSION_ENGINE.md`) |
| 8 | M111-M117 | Frontend foundation |
| 9 | M118-M138 | Frontend screens (`UI_UX_SPECIFICATION.md`) |
| 10 | M139-M156 | Digital Twin 3D engine (`DIGITAL_TWIN_EXPERIENCE.md`) |
| 11 | M157-M160 | Real-time integration |
| 12 | M161-M164 | Emergency response end-to-end |
| 13 | M165-M170 | Compliance & hardening |

---

## Phase 0 — Foundations & Tooling (M1-M8)

### M1. Initialize the Monorepo Structure
- **Objective:** Create the top-level folder layout exactly as specified in `ARCHITECTURE.md` §23.2.
- **Files:** `apps/`, `services/`, `libs/`, `infra/`, `docs/` (existing), `.github/workflows/` — each with a placeholder `.gitkeep` or `README.md`.
- **Tests:** A shell script `scripts/verify-structure.sh` asserting every required top-level directory exists.
- **Expected Output:** `tree -L 2` shows the exact structure from §23.2.
- **Acceptance Criteria:** All 5 top-level dirs exist; `verify-structure.sh` passes; committed to git.
- **Dependencies:** None.
- **Risk:** Low — pure scaffolding.
- **Estimated Time:** 1h

### M2. Build the Shared Service Template Scaffold
- **Objective:** Create `libs/service-template/` — the boilerplate every backend service copies from (health check endpoint, structured logging, metrics endpoint stub, per `ARCHITECTURE.md` §23.3).
- **Files:** `libs/service-template/src/{api,domain,integrations,config}/`, `libs/service-template/Dockerfile`, `libs/service-template/service.yaml`.
- **Tests:** A generic test asserting `/health` returns `200 {"status":"ok"}` when the template is instantiated stand-alone.
- **Expected Output:** Running the template service locally responds to `GET /health`.
- **Acceptance Criteria:** Health check works; logging emits structured JSON; `service.yaml` schema documented.
- **Dependencies:** M1.
- **Risk:** Medium — gets this wrong and every later service inherits the mistake.
- **Estimated Time:** 3h

### M3. Configure Docker Compose Local Dev Environment (Stub Services)
- **Objective:** `infra/docker-compose/docker-compose.yml` bringing up empty placeholder containers for every service named in `ARCHITECTURE.md` §23.2, each just running the M2 template.
- **Files:** `infra/docker-compose/docker-compose.yml`.
- **Tests:** `docker-compose up` exits 0 and all containers report healthy.
- **Expected Output:** `docker-compose ps` shows every service `Up (healthy)`.
- **Acceptance Criteria:** All 14 services listed in §8.1's table start; no port conflicts; one command (`docker-compose up`) is the full entry point.
- **Dependencies:** M2.
- **Risk:** Low.
- **Estimated Time:** 2h

### M4. Stand Up PostgreSQL + TimescaleDB Container
- **Objective:** Add the Postgres/Timescale container to `docker-compose.yml`, no schema yet.
- **Files:** `infra/docker-compose/docker-compose.yml` (postgres service block), `infra/docker-compose/.env.example`.
- **Tests:** `psql` connection test script confirming `SELECT 1` succeeds and `timescaledb` extension is installable.
- **Expected Output:** `docker exec -it postgres psql -U aegis -c "SELECT extname FROM pg_available_extensions WHERE extname='timescaledb'"` returns a row.
- **Acceptance Criteria:** Container starts; connection succeeds; TimescaleDB extension available (not yet enabled — that's M9).
- **Dependencies:** M3.
- **Risk:** Low.
- **Estimated Time:** 1h

### M5. Stand Up Neo4j Container
- **Objective:** Add the Neo4j container to `docker-compose.yml` for the Knowledge Graph (`KNOWLEDGE_GRAPH.md`).
- **Files:** `infra/docker-compose/docker-compose.yml` (neo4j service block).
- **Tests:** A connection script running `RETURN 1` via the Bolt driver.
- **Expected Output:** Neo4j Browser reachable at `localhost:7474`; test query returns `1`.
- **Acceptance Criteria:** Container starts; Bolt connection succeeds; credentials documented in `.env.example`.
- **Dependencies:** M3.
- **Risk:** Low.
- **Estimated Time:** 1h

### M6. Stand Up Kafka/Redpanda Container
- **Objective:** Add the Event Backbone broker (`ARCHITECTURE.md` §10.2) to `docker-compose.yml`.
- **Files:** `infra/docker-compose/docker-compose.yml` (redpanda service block).
- **Tests:** A script producing and consuming one message on a test topic.
- **Expected Output:** `rpk topic list` shows the test topic; produced message is consumed back successfully.
- **Acceptance Criteria:** Broker starts; produce/consume round-trip works; schema registry endpoint reachable.
- **Dependencies:** M3.
- **Risk:** Low.
- **Estimated Time:** 2h

### M7. Configure CI Pipeline Skeleton
- **Objective:** `.github/workflows/ci.yml` running lint + build on every PR, per `ARCHITECTURE.md` §25.1's pipeline (schema/test stages come later, once there's something to test).
- **Files:** `.github/workflows/ci.yml`.
- **Tests:** The workflow itself, run against a trivial PR.
- **Expected Output:** A GitHub Actions run shows green lint+build checks.
- **Acceptance Criteria:** Pipeline triggers on PR; fails correctly on an intentionally broken commit (verified once); passes on a clean one.
- **Dependencies:** M1.
- **Risk:** Low.
- **Estimated Time:** 2h

### M8. Configure Shared Lint/Format/TypeScript Base Config
- **Objective:** `libs/schemas/` package plus root-level ESLint/Prettier/`tsconfig.base.json` shared across `apps/` and `services/`.
- **Files:** `.eslintrc.js`, `.prettierrc`, `tsconfig.base.json`, `libs/schemas/package.json`.
- **Tests:** `npm run lint` against a sample file with a known violation, confirming it's caught.
- **Expected Output:** Lint command exits non-zero on a violation, zero on clean code.
- **Acceptance Criteria:** Config applies consistently to both `apps/web` and any `services/*` written in TypeScript.
- **Dependencies:** M1.
- **Risk:** Low.
- **Estimated Time:** 1h

---

## Phase 1 — Database Layer (M9-M44)
Implements `DATABASE_SCHEMA.md` table by table. Migrations live in `services/*/migrations/` per-service where a table is service-owned, or `infra/docker-compose/db-init/` for shared bootstrap DDL (extensions, enums, lookups).

### M9. Enable Postgres Extensions
- **Objective:** Run `DATABASE_SCHEMA.md` §1's `CREATE EXTENSION` statements (timescaledb, pgcrypto, pg_trgm, btree_gist, citext).
- **Files:** `infra/docker-compose/db-init/001_extensions.sql`.
- **Tests:** Query `pg_extension` confirming all 5 are installed.
- **Expected Output:** `\dx` in psql lists all 5 extensions.
- **Acceptance Criteria:** All extensions enabled; migration is idempotent (`IF NOT EXISTS`).
- **Dependencies:** M4.
- **Risk:** Low.
- **Estimated Time:** 1h

### M10. Create Global Trigger Functions
- **Objective:** Implement `set_updated_at()`, `audit_row_change()`, `prevent_mutation()` (§1.1).
- **Files:** `infra/docker-compose/db-init/002_trigger_functions.sql`.
- **Tests:** Unit-test each function in isolation against a scratch table (create a temp table, attach the trigger, verify behavior).
- **Expected Output:** A test table with `set_updated_at` attached shows `updated_at` change on `UPDATE`.
- **Acceptance Criteria:** All 3 functions created; each individually verified against a scratch table before being relied on elsewhere.
- **Dependencies:** M9.
- **Risk:** Medium — every later table depends on these being correct.
- **Estimated Time:** 2h

### M11. Create Enum Types
- **Objective:** All enum types from §2 (`severity_level`, `incident_status`, etc.).
- **Files:** `infra/docker-compose/db-init/003_enums.sql`.
- **Tests:** Query `pg_type` confirming all 14 enums exist with correct labels.
- **Expected Output:** `\dT+` lists all enums with their value sets.
- **Acceptance Criteria:** All enums from §2 present with exact label sets matching the doc.
- **Dependencies:** M9.
- **Risk:** Low.
- **Estimated Time:** 1h

### M12. Create Lookup Tables
- **Objective:** `roles`, `equipment_types`, `sensor_types`, `permit_types`, `maintenance_types`, `employers` (§3).
- **Files:** `infra/docker-compose/db-init/004_lookup_tables.sql`.
- **Tests:** Insert/select round-trip test per table; uniqueness constraint violation test on `name`.
- **Expected Output:** Seeded with the example values from §3 (e.g., roles: operator, supervisor, safety_officer...).
- **Acceptance Criteria:** All 6 tables created; seeded; unique constraints verified to reject duplicates.
- **Dependencies:** M11.
- **Risk:** Low.
- **Estimated Time:** 2h

### M13. Create `plants` Table
- **Objective:** §4.1's table + `set_updated_at` trigger.
- **Files:** `services/digital-twin/migrations/001_plants.sql`.
- **Tests:** Insert a plant; verify `updated_at` changes on update; verify `code` uniqueness constraint.
- **Expected Output:** One demo plant row exists after seeding.
- **Acceptance Criteria:** Table matches §4.1 exactly; trigger fires; unique constraint enforced.
- **Dependencies:** M10.
- **Risk:** Low.
- **Estimated Time:** 1h

### M14. Create `buildings` Table
- **Objective:** §4.2's table, FK to `plants`, `ON DELETE CASCADE`.
- **Files:** `services/digital-twin/migrations/002_buildings.sql`.
- **Tests:** Insert building under a plant; verify cascade delete removes buildings when plant deleted (on a scratch row); verify `idx_buildings_plant_id` exists via `EXPLAIN`.
- **Expected Output:** `EXPLAIN SELECT * FROM buildings WHERE plant_id = X` uses the index.
- **Acceptance Criteria:** FK + cascade verified; index present and used.
- **Dependencies:** M13.
- **Risk:** Low.
- **Estimated Time:** 1h

### M15. Create `zones` Table
- **Objective:** §4.3's table including the partial index on `hazard_class`.
- **Files:** `services/digital-twin/migrations/003_zones.sql`.
- **Tests:** Insert zones with and without `hazard_class`; confirm partial index only covers non-null rows via `pg_indexes`/`EXPLAIN`.
- **Expected Output:** Query filtering on hazard class uses `idx_zones_hazard_class`.
- **Acceptance Criteria:** Table + both indexes present; partial index confirmed via query plan.
- **Dependencies:** M14.
- **Risk:** Low.
- **Estimated Time:** 1h

### M16. Create `equipment` Table
- **Objective:** §5.1's supertype table including `upstream_equipment_id` self-reference and `criticality` CHECK constraint.
- **Files:** `services/digital-twin/migrations/004_equipment.sql`.
- **Tests:** Insert equipment with self-referencing upstream; verify `criticality` CHECK rejects value `6`; verify `RESTRICT` blocks deleting a zone with equipment in it.
- **Expected Output:** Attempting to delete a referenced zone raises a foreign-key-violation error.
- **Acceptance Criteria:** All constraints from §5.1 verified individually.
- **Dependencies:** M15, M12 (equipment_types).
- **Risk:** Medium — the self-reference and RESTRICT behavior are easy to get backwards.
- **Estimated Time:** 3h

### M17. Create `machines` Subtype Table
- **Objective:** §5.2's class-table-inheritance extension table, shared PK, `ON DELETE CASCADE`.
- **Files:** `services/digital-twin/migrations/005_machines.sql`.
- **Tests:** Insert equipment + machine pair; delete the equipment row, verify the machine row cascades away.
- **Expected Output:** Deleting `equipment.id=X` also removes `machines` row with the same id.
- **Acceptance Criteria:** Shared-PK pattern verified; cascade direction confirmed (opposite of M16's equipment/zone RESTRICT — intentionally different, per §5.2's explanation).
- **Dependencies:** M16.
- **Risk:** Low.
- **Estimated Time:** 1h

### M18. Create `sensors` Table
- **Objective:** §5.3's table including the `chk_sensor_monitors_something` CHECK constraint.
- **Files:** `services/ingestion-gateway/migrations/001_sensors.sql`.
- **Tests:** Attempt insert with both `equipment_id` and `zone_id` NULL — must fail; attempt with one set — must succeed.
- **Expected Output:** The invalid insert raises a check-violation error.
- **Acceptance Criteria:** CHECK constraint verified in both directions; both partial indexes present.
- **Dependencies:** M16, M15, M12 (sensor_types).
- **Risk:** Low.
- **Estimated Time:** 2h

### M19. Create `users` Table
- **Objective:** §6.1's table with CITEXT email and the audit trigger attached.
- **Files:** `services/identity-rbac/migrations/001_users.sql`.
- **Tests:** Insert two users with differently-cased identical emails — second insert must fail on uniqueness; verify an `UPDATE` writes a row into `audit_logs` (once M34 exists — stub-verify via a temp audit table until then).
- **Expected Output:** `'A@x.com'` and `'a@x.com'` collide on insert.
- **Acceptance Criteria:** CITEXT case-insensitivity verified; audit trigger attached (full verification deferred to M34's integration test).
- **Dependencies:** M12 (roles), M10.
- **Risk:** Low.
- **Estimated Time:** 2h

### M20. Create `workers` Table
- **Objective:** §6.2's table including the JSONB `certifications` GIN index.
- **Files:** `services/identity-rbac/migrations/002_workers.sql`.
- **Tests:** Insert a worker with a certifications array; query using the GIN index (`jsonb_path_ops`) and confirm it's used via `EXPLAIN`.
- **Expected Output:** A `@>` containment query on `certifications` hits the GIN index.
- **Acceptance Criteria:** Optional `user_id` FK verified nullable; GIN index confirmed used.
- **Dependencies:** M19, M12 (employers).
- **Risk:** Low.
- **Estimated Time:** 2h

### M21. Create `user_role_scopes` Table
- **Objective:** §6.3's RBAC junction table including `chk_zone_implies_plant`.
- **Files:** `services/identity-rbac/migrations/003_user_role_scopes.sql`.
- **Tests:** Attempt a zone-scoped grant with `plant_id = NULL` — must fail; grant with both set — must succeed; verify `UNIQUE` prevents duplicate grants.
- **Expected Output:** The invalid zone-without-plant insert raises a check violation.
- **Acceptance Criteria:** All three constraints (CHECK, UNIQUE, audit trigger) individually verified.
- **Dependencies:** M20, M15, M13.
- **Risk:** Medium — this table is the entire RBAC enforcement foundation; a bug here is a security bug.
- **Estimated Time:** 3h

### M22. Create `shifts` and `shift_assignments` Tables
- **Objective:** §6.4's tables including the `EXCLUDE USING gist` overlap constraint.
- **Files:** `services/identity-rbac/migrations/004_shifts.sql`.
- **Tests:** Assign a worker to two overlapping shift periods — second insert must fail with an exclusion-violation error; non-overlapping assignments must succeed.
- **Expected Output:** Overlapping assignment attempt raises `23P01` (exclusion_violation).
- **Acceptance Criteria:** Exclusion constraint verified with an actual overlap test case, not just schema presence.
- **Dependencies:** M20, M13.
- **Risk:** Medium — GiST exclusion constraints are easy to configure subtly wrong.
- **Estimated Time:** 2h

### M23. Create `permits` Table
- **Objective:** §7's table including `chk_permit_validity_window` and the partial active-permit index.
- **Files:** `services/incident-service/migrations/001_permits.sql`.
- **Tests:** Insert with `valid_to < valid_from` — must fail; insert valid — must succeed; verify partial index used for an active-permit lookup query.
- **Expected Output:** `EXPLAIN` on the active-permit query shows `idx_permits_active`.
- **Acceptance Criteria:** Validity CHECK verified; audit trigger attached and fires on status change.
- **Dependencies:** M20, M15, M16, M12 (permit_types), M19.
- **Risk:** Low.
- **Estimated Time:** 2h

### M24. Create `maintenance_records` Table
- **Objective:** §8's table (note: `related_prediction_id` FK added later in M... — deferred per the doc's own forward-reference note; add as a nullable column now, constraint later once `predictions` exists).
- **Files:** `services/predictive-risk-engine/migrations/001_maintenance_records.sql` (or the maintenance-owning service if split out — see Phase 7 note on agent-to-service mapping).
- **Tests:** Insert/update lifecycle test (scheduled → in_progress → completed); verify partial index on active statuses.
- **Expected Output:** Querying `status IN ('scheduled','in_progress')` uses `idx_maintenance_status`.
- **Acceptance Criteria:** Table created; FK constraint to `predictions` added in a follow-up migration once M29 exists (tracked, not silently forgotten).
- **Dependencies:** M16, M12 (maintenance_types), M20, M19.
- **Risk:** Low.
- **Estimated Time:** 2h

### M25. Create `incidents` Table (Partitioned)
- **Objective:** §9's table with `RANGE (created_at)` monthly partitioning.
- **Files:** `services/incident-service/migrations/002_incidents.sql`, `services/incident-service/migrations/002a_incidents_partitions.sql` (initial 3 months of partitions).
- **Tests:** Insert into current month; verify row lands in the correct child partition (`\d+ incidents` shows partition list); insert into a month with no partition — must fail cleanly, confirming the need for M42's pg_partman automation.
- **Expected Output:** `SELECT tableoid::regclass FROM incidents WHERE id = X` shows the expected partition name.
- **Acceptance Criteria:** Partitioning confirmed functional; the "no future partition" failure mode observed once, deliberately, to justify M42.
- **Dependencies:** M13, M15, M16, M19.
- **Risk:** Medium — partition-maintenance gaps are a real, documented production failure mode (§22.5).
- **Estimated Time:** 3h

### M26. Create `incident_timeline_events` Table
- **Objective:** §9.1's append-only table with `prevent_mutation()` trigger attached.
- **Files:** `services/incident-service/migrations/003_incident_timeline_events.sql`.
- **Tests:** Insert an event; attempt `UPDATE` and `DELETE` — both must fail with the custom exception from `prevent_mutation()`.
- **Expected Output:** `UPDATE incident_timeline_events SET ... ` raises the "append-only table" exception.
- **Acceptance Criteria:** Both UPDATE and DELETE independently verified blocked.
- **Dependencies:** M25, M10.
- **Risk:** Low.
- **Estimated Time:** 1h

### M27. Create `risk_scores` Hypertable
- **Objective:** §10's hypertable via `create_hypertable()`, daily chunks.
- **Files:** `services/predictive-risk-engine/migrations/001_risk_scores.sql`.
- **Tests:** Insert rows spanning 3 days; verify 3 chunks exist via `timescaledb_information.chunks`.
- **Expected Output:** `SELECT show_chunks('risk_scores')` lists one chunk per day inserted.
- **Acceptance Criteria:** Hypertable conversion confirmed; `chk_risk_target` CHECK verified (equipment or zone required).
- **Dependencies:** M16, M15.
- **Risk:** Low.
- **Estimated Time:** 2h

### M28. Create `alerts` Table (Partitioned) + `pg_notify` Trigger
- **Objective:** §11's table plus the `notify_new_alert()` trigger.
- **Files:** `services/notification-service/migrations/001_alerts.sql`.
- **Tests:** Insert an alert while a `LISTEN aegis_new_alert` session is open; verify the notification payload arrives with correct `id`/`severity`.
- **Expected Output:** A test script using `LISTEN`/`NOTIFY` receives the JSON payload within milliseconds of insert.
- **Acceptance Criteria:** Trigger fires on every insert; payload shape matches §11's spec exactly.
- **Dependencies:** M16, M15, M18, M25.
- **Risk:** Medium — first real-time bridge in the system; worth verifying carefully.
- **Estimated Time:** 2h

### M29. Create `predictions` Hypertable
- **Objective:** §12's hypertable, including the `idx_predictions_pending_outcome` partial index.
- **Files:** `services/predictive-risk-engine/migrations/002_predictions.sql`.
- **Tests:** Insert a prediction with `actual_outcome IS NULL`; verify it appears in the pending-outcome partial-index query; update it with an outcome; verify it drops out.
- **Expected Output:** Pending-outcome count decreases by 1 after the update.
- **Acceptance Criteria:** Hypertable confirmed; partial index behavior verified end to end.
- **Dependencies:** M16.
- **Risk:** Low.
- **Estimated Time:** 2h
- **Follow-up:** Add the deferred `maintenance_records.related_prediction_id` FK constraint now (M24's note).

### M30. Create `playbooks` and `playbook_steps` Tables
- **Objective:** §13's template tables including the `UNIQUE (playbook_id, step_order)` constraint.
- **Files:** `services/agentic-orchestrator/migrations/001_playbooks.sql`.
- **Tests:** Insert a playbook with 3 steps out of order (step_order 2, 1, 3); verify retrieval `ORDER BY step_order` returns them correctly sequenced.
- **Expected Output:** Steps come back in logical order regardless of insert order.
- **Acceptance Criteria:** `autonomy_tier` enum values verified against §15.2's four tiers.
- **Dependencies:** M19.
- **Risk:** Low.
- **Estimated Time:** 2h

### M31. Create `emergency_events` and `emergency_event_steps` Tables
- **Objective:** §13's runtime-instance tables, both audit-triggered.
- **Files:** `services/agentic-orchestrator/migrations/002_emergency_events.sql`.
- **Tests:** Insert an event with a step whose `playbook_step_id IS NULL` (manual-response path) — must succeed, per the doc's explicit nullable design.
- **Expected Output:** A manual-response emergency event with an ad hoc step inserts cleanly.
- **Acceptance Criteria:** Both nullable-FK escape hatches (§13's note) verified functional, not just present in schema.
- **Dependencies:** M30, M25, M13, M15.
- **Risk:** Medium — the nullable relationships here are subtle; easy to accidentally make one NOT NULL.
- **Estimated Time:** 2h

### M32. Create `cameras` Table and `camera_events` Hypertable
- **Objective:** §14's tables.
- **Files:** `services/computer-vision/migrations/001_cameras.sql`.
- **Tests:** Insert camera-events across 2 days; verify hypertable chunking; verify partial index on `confidence >= 0.7`.
- **Expected Output:** High-confidence-only query uses `idx_camera_events_high_confidence`.
- **Acceptance Criteria:** Hypertable + both indexes confirmed.
- **Dependencies:** M15.
- **Risk:** Low.
- **Estimated Time:** 2h

### M33. Create `ppe_violations` Hypertable
- **Objective:** §15's hypertable, nullable `worker_id` handled per the doc's ethics-note design.
- **Files:** `services/computer-vision/migrations/002_ppe_violations.sql`.
- **Tests:** Insert a violation with `worker_id = NULL` (unattributed) — must succeed and still be queryable by zone.
- **Expected Output:** Zone-level query returns the unattributed violation correctly.
- **Acceptance Criteria:** Nullable-worker path explicitly tested, not just schema-permitted.
- **Dependencies:** M32, M15, M20.
- **Risk:** Low.
- **Estimated Time:** 1h

### M34. Create `audit_logs` Hypertable + Immutability Trigger
- **Objective:** §16's table — the most important trigger in the schema.
- **Files:** `infra/docker-compose/db-init/005_audit_logs.sql`.
- **Tests:** Insert a row; attempt `UPDATE` and `DELETE` — both must fail; verify M19's users-table `UPDATE` correctly produces a new row here (closing M19's deferred verification).
- **Expected Output:** Both mutation attempts raise the append-only exception; the M19 audit round-trip is confirmed working end-to-end.
- **Acceptance Criteria:** Immutability verified; hypertable with monthly chunks confirmed; M19's deferred test now fully closed out.
- **Dependencies:** M19, M10.
- **Risk:** High — this is the compliance backbone (`NFR-17`); get it wrong and the whole audit guarantee is fiction.
- **Estimated Time:** 2h

### M35. Create `notifications` Table (Partitioned)
- **Objective:** §17's table.
- **Files:** `services/notification-service/migrations/002_notifications.sql`.
- **Tests:** Lifecycle test (pending → sent → delivered → acknowledged); verify partial pending-index.
- **Expected Output:** Status transitions persist correctly; pending-query uses the partial index.
- **Acceptance Criteria:** Both nullable FKs (`related_incident_id`/`related_alert_id`) verified independently settable.
- **Dependencies:** M19, M25, M28.
- **Risk:** Low.
- **Estimated Time:** 1h

### M36. Create `reports` Table
- **Objective:** §18's table.
- **Files:** `services/incident-service/migrations/004_reports.sql` (or a dedicated reporting service if split later).
- **Tests:** Insert with `date_range_end < date_range_start` — must fail on the CHECK constraint.
- **Expected Output:** Invalid date range insert raises a check violation.
- **Acceptance Criteria:** CHECK verified; `schedule_cron` nullable-vs-set both paths tested.
- **Dependencies:** M19, M13.
- **Risk:** Low.
- **Estimated Time:** 1h

### M37. Create `weather_observations` Hypertable
- **Objective:** §19's hypertable.
- **Files:** `services/ingestion-gateway/migrations/002_weather.sql`.
- **Tests:** Insert with `wind_direction_deg = 400` — must fail on the CHECK constraint (0-359 range).
- **Expected Output:** Out-of-range wind direction insert fails.
- **Acceptance Criteria:** Hypertable + CHECK constraint both verified.
- **Dependencies:** M13.
- **Risk:** Low.
- **Estimated Time:** 1h

### M38. Create `sensor_readings` Hypertable (2D Partitioned)
- **Objective:** §20's hypertable with the additional `sensor_id` space dimension via `add_dimension()`.
- **Files:** `services/ingestion-gateway/migrations/003_sensor_readings.sql`.
- **Tests:** Insert readings for 3 different sensors across 2 days; verify chunk count reflects both time AND space partitioning (more chunks than a time-only hypertable would produce).
- **Expected Output:** `timescaledb_information.chunks` shows multiple chunks per day, split by sensor space partition.
- **Acceptance Criteria:** 2D partitioning confirmed via chunk inspection, not just successful insert.
- **Dependencies:** M18.
- **Risk:** Medium — this is the highest-volume table in the schema; getting the space-partitioning wrong is expensive to fix later.
- **Estimated Time:** 3h

### M39. Create `machine_state_history` Hypertable
- **Objective:** §21's hypertable (time-only partitioning, per the doc's explicit contrast with M38).
- **Files:** `services/predictive-risk-engine/migrations/003_machine_state_history.sql`.
- **Tests:** Insert states across 2 days; verify time-only chunking (no space dimension).
- **Expected Output:** Chunk count matches days inserted, not multiplied by machine count.
- **Acceptance Criteria:** Confirmed distinct from M38's 2D approach, intentionally.
- **Dependencies:** M17.
- **Risk:** Low.
- **Estimated Time:** 1h

### M40. Set Up Continuous Aggregates for `sensor_readings`
- **Objective:** §22.4's `sensor_readings_1min` and `sensor_readings_1hour` materialized views.
- **Files:** `services/ingestion-gateway/migrations/004_continuous_aggregates.sql`.
- **Tests:** Insert raw readings; wait for (or manually trigger) aggregate refresh; verify the 1-minute rollup reflects correct avg/min/max.
- **Expected Output:** Querying `sensor_readings_1min` for a known input set returns mathematically correct aggregates.
- **Acceptance Criteria:** Both aggregate views created and refresh-policy attached; correctness verified against hand-computed expected values.
- **Dependencies:** M38.
- **Risk:** Medium — a subtly wrong aggregate is worse than an obviously broken one.
- **Estimated Time:** 2h

### M41. Configure Compression Policies (All Hypertables)
- **Objective:** §22.2's `add_compression_policy()` calls for every hypertable.
- **Files:** `infra/docker-compose/db-init/006_compression_policies.sql`.
- **Tests:** Manually age a chunk past its compression window (or use Timescale's manual `compress_chunk()`) and verify storage size drops.
- **Expected Output:** `SELECT compression_status FROM chunk_compression_stats(...)` shows compressed chunks.
- **Acceptance Criteria:** Every hypertable from M27/29/32/33/34/37/38/39 has a compression policy attached and manually verified once.
- **Dependencies:** M27, M29, M32, M33, M34, M37, M38, M39.
- **Risk:** Low.
- **Estimated Time:** 2h

### M42. Configure Retention Policies + pg_partman for Native-Partitioned Tables
- **Objective:** §22.3's `add_retention_policy()` calls, plus §22.5's `pg_partman` setup for `incidents`/`alerts`/`notifications` — directly resolving M25's observed failure mode.
- **Files:** `infra/docker-compose/db-init/007_retention_and_partman.sql`.
- **Tests:** Verify `pg_partman`'s `create_parent()` call produces 3 pre-made future partitions; re-attempt M25's "insert into a future month with no partition" test — must now succeed.
- **Expected Output:** The previously-failing future-month insert from M25 now works.
- **Acceptance Criteria:** Retention policies present on every hypertable except `audit_logs` (deliberately excluded, per `NFR-17`); pg_partman confirmed auto-creating partitions.
- **Dependencies:** M25, M28, M35, M41.
- **Risk:** High — an unmonitored partition-maintenance gap is a real outage mode (§22.5's explicit warning).
- **Estimated Time:** 3h

### M43. Write the Seed-Data Script
- **Objective:** A demo dataset: 1 plant, 3 buildings, 10 zones, 40 equipment (mixed valves/machines/pipelines), 100 sensors, 5 workers, 2 permits.
- **Files:** `infra/docker-compose/db-init/999_seed_demo_data.sql`, `scripts/reseed-demo.sh`.
- **Tests:** Run the script twice — must be idempotent (no duplicate-key errors on re-run).
- **Expected Output:** `SELECT count(*) FROM equipment` returns 40 after running.
- **Acceptance Criteria:** Idempotent; referentially consistent (every FK resolves); representative of the topology `KNOWLEDGE_GRAPH.md`'s examples assume (a linear-ish process line with V-12, RV-9, etc. as named entities).
- **Dependencies:** M13-M23 (every table seeded touches).
- **Risk:** Medium — this dataset is what every later demo and every later milestone's manual testing depends on.
- **Estimated Time:** 3h

### M44. Write the Database Integration Test Suite
- **Objective:** A consolidated test suite (`services/*/tests/db/`) running every constraint/trigger verification from M9-M43 as a single CI-runnable suite, rather than leaving them as one-off manual checks.
- **Files:** `libs/schemas/tests/db-integration/*.test.ts` (or per-service, matching each table's owning service).
- **Tests:** Every CHECK, FK, trigger, and index-usage assertion from M9-M43, automated.
- **Expected Output:** `npm run test:db` passes fully against a freshly-seeded local database.
- **Acceptance Criteria:** 100% of the manually-verified behaviors from this phase now run automatically in CI on every PR touching a migration file.
- **Dependencies:** M9-M43 (all of Phase 1).
- **Risk:** Medium — without this, every future migration risks silently breaking an earlier constraint.
- **Estimated Time:** 3h

---

## Phase 2 — Core Backend Service Skeletons (M45-M54)
Implements `ARCHITECTURE.md` §8.1's service table, each built up from the M2 template.

### M45. Scaffold Identity & RBAC Service
- **Objective:** A real service (not the bare template) connecting to `users`/`workers`/`user_role_scopes`.
- **Files:** `services/identity-rbac/src/domain/user.repository.ts`, `services/identity-rbac/src/api/health.controller.ts`.
- **Tests:** Integration test hitting `/health` and a DB-connectivity check endpoint.
- **Expected Output:** `/health` returns `200` with a DB-connection-ok flag.
- **Acceptance Criteria:** Service starts against the real Postgres container; connects successfully.
- **Dependencies:** M19, M2.
- **Risk:** Low.
- **Estimated Time:** 2h

### M46. Implement User Login (JWT Issuance)
- **Objective:** `POST /auth/login` — email+password against `users.password_hash`, returns a short-lived JWT (`ARCHITECTURE.md` §20.1).
- **Files:** `services/identity-rbac/src/api/auth.controller.ts`, `services/identity-rbac/src/domain/token.service.ts`.
- **Tests:** Correct credentials → 200 + valid JWT; wrong password → 401; JWT decodes with correct claims (`user_id`, `default_role_id`).
- **Expected Output:** A `curl` login request returns a decodable JWT.
- **Acceptance Criteria:** Password verified via `pgcrypto`; JWT expiry matches the 5-15 min window from §20.1.
- **Dependencies:** M45.
- **Risk:** Medium — first real auth code path; security-sensitive.
- **Estimated Time:** 3h

### M47. Implement OIDC Federation Stub
- **Objective:** A pluggable federation interface (§20.1) with one mock provider for local dev — real Azure AD/Okta wiring deferred, but the seam exists.
- **Files:** `services/identity-rbac/src/domain/oidc-provider.interface.ts`, `services/identity-rbac/src/integrations/mock-oidc.provider.ts`.
- **Tests:** Mock-provider login round-trip returns a valid session.
- **Expected Output:** A simulated OIDC callback issues a JWT identical in shape to M46's.
- **Acceptance Criteria:** Interface is provider-agnostic; swapping the mock for a real provider requires no changes to `auth.controller.ts`.
- **Dependencies:** M46.
- **Risk:** Low.
- **Estimated Time:** 2h

### M48. Implement RBAC Middleware
- **Objective:** A `(Role, Resource Scope)` permission check middleware (§21.1) usable by any service.
- **Files:** `libs/service-template/src/middleware/rbac.middleware.ts`.
- **Tests:** A user scoped to Zone A denied access to a Zone B resource; a plant-wide-scoped Safety Officer allowed access to both.
- **Expected Output:** 403 for out-of-scope access, 200 for in-scope.
- **Acceptance Criteria:** Both nested-scope cases (plant-only grant, zone-specific grant) independently tested.
- **Dependencies:** M21, M46.
- **Risk:** High — this is the single enforcement point `NFR-13` depends on.
- **Estimated Time:** 3h

### M49. Scaffold API Gateway
- **Objective:** A gateway service routing `/api/*` to Identity for now (more routes added as later phases add services).
- **Files:** `services/api-gateway/src/routes/auth.routes.ts`.
- **Tests:** A proxied login request through the gateway succeeds identically to calling Identity directly.
- **Expected Output:** `curl gateway/api/auth/login` behaves identically to `curl identity/auth/login`.
- **Acceptance Criteria:** Gateway correctly forwards and returns identity-service responses unmodified.
- **Dependencies:** M46.
- **Risk:** Low.
- **Estimated Time:** 2h

### M50. Scaffold Realtime Gateway (WebSocket Echo Test)
- **Objective:** A bare WebSocket server proving the connection/subscription pattern before any real data flows through it (`ARCHITECTURE.md` §11.2).
- **Files:** `services/realtime-gateway/src/ws-server.ts`.
- **Tests:** A test client connects, subscribes to a test channel, sends a message, receives it echoed back.
- **Expected Output:** WebSocket echo round-trip succeeds.
- **Acceptance Criteria:** Connection/subscribe/publish/receive cycle works with more than one concurrent client.
- **Dependencies:** M2.
- **Risk:** Low.
- **Estimated Time:** 2h

### M51. Scaffold Ingestion Gateway Service
- **Objective:** A bare service ready to host protocol adapters (§17.2) — no adapter logic yet, just the shell and its connection to `sensor_readings`.
- **Files:** `services/ingestion-gateway/src/api/health.controller.ts`.
- **Tests:** Health check + DB-connectivity check.
- **Expected Output:** `/health` returns 200 with DB-connected flag.
- **Acceptance Criteria:** Service starts; can write a test row directly to `sensor_readings`.
- **Dependencies:** M38.
- **Risk:** Low.
- **Estimated Time:** 1h

### M52. Scaffold Incident Service (CRUD Skeleton)
- **Objective:** Basic create/read/update endpoints against `incidents` (no business logic yet — that's Phase 12).
- **Files:** `services/incident-service/src/api/incidents.controller.ts`.
- **Tests:** Create an incident via API, read it back, update its status.
- **Expected Output:** `POST /incidents` returns the created row; `GET /incidents/:id` returns it.
- **Acceptance Criteria:** Full CRUD round-trip verified against the real partitioned table.
- **Dependencies:** M25.
- **Risk:** Low.
- **Estimated Time:** 2h

### M53. Scaffold Notification Service (In-App Channel Only)
- **Objective:** A minimal notification dispatcher — one channel (`in_app`) end to end, other channels (SMS/push/voice, §11.3) deferred.
- **Files:** `services/notification-service/src/domain/dispatch.service.ts`, `services/notification-service/src/channels/in-app.channel.ts`.
- **Tests:** Creating a `notifications` row triggers a dispatch that updates `status` to `sent`.
- **Expected Output:** A test notification transitions `pending → sent` automatically.
- **Acceptance Criteria:** Single-channel dispatch loop verified; channel interface is pluggable for later additions.
- **Dependencies:** M35.
- **Risk:** Low.
- **Estimated Time:** 2h

### M54. Scaffold Audit Log Service (Consumer Writing to `audit_logs`)
- **Objective:** A dedicated read-side service exposing `audit_logs` query endpoints — the write side already exists via M34's trigger; this is the query API.
- **Files:** `services/audit-log/src/api/audit.controller.ts`.
- **Tests:** Query by resource_type/resource_id returns matching audit rows.
- **Expected Output:** `GET /audit?resource_type=users&resource_id=1` returns that user's change history.
- **Acceptance Criteria:** Read-only service; confirms it cannot mutate `audit_logs` even with a bug (no write path exists in this service at all).
- **Dependencies:** M34.
- **Risk:** Low.
- **Estimated Time:** 1h

---

## Phase 3 — Event Backbone (M55-M58)
Implements `ARCHITECTURE.md` §10.

### M55. Define Core Event Schemas
- **Objective:** Avro/JSON schemas for `telemetry.raw`, `anomaly.detected`, `risk.updated` (§10.3's topic table).
- **Files:** `libs/schemas/events/telemetry-raw.schema.json`, `libs/schemas/events/anomaly-detected.schema.json`, `libs/schemas/events/risk-updated.schema.json`.
- **Tests:** Schema-validate a sample payload against each schema; reject a malformed one.
- **Expected Output:** Valid payload passes; a payload missing a required field fails validation.
- **Acceptance Criteria:** All 3 schemas match the field shapes implied by their consuming tables (`sensor_readings`, `alerts`, `risk_scores`).
- **Dependencies:** M6.
- **Risk:** Low.
- **Estimated Time:** 2h

### M56. Register Schemas with the Schema Registry + CI Compatibility Check
- **Objective:** Push M55's schemas to the registry; add a CI step (`ARCHITECTURE.md` §25.1) failing the build on a backward-incompatible schema change.
- **Files:** `.github/workflows/ci.yml` (schema-check job), `scripts/register-schemas.sh`.
- **Tests:** Attempt a deliberately breaking schema change in a test PR — CI must fail.
- **Expected Output:** The breaking-change PR shows a red CI check specifically flagging schema incompatibility.
- **Acceptance Criteria:** Compatibility check verified against one real breaking change, not just present in config.
- **Dependencies:** M55, M7.
- **Risk:** Medium — this is what makes independent service deployability (`NFR-14`) real rather than assumed.
- **Estimated Time:** 2h

### M57. Create Kafka Topics via Infrastructure-as-Code
- **Objective:** A declarative topic-creation script (partition count, retention per §10.3's table) rather than manual topic creation.
- **Files:** `infra/docker-compose/kafka-topics.sh`, `infra/terraform/kafka-topics.tf` (stub for later cloud deployment).
- **Tests:** Run the script; verify all topics exist with correct partition/retention config via `rpk topic describe`.
- **Expected Output:** `rpk topic list` shows every topic from §10.3.
- **Acceptance Criteria:** Retention settings match the doc exactly per topic (7 years for `incident.*`/`action.*`, shorter for raw telemetry).
- **Dependencies:** M6.
- **Risk:** Low.
- **Estimated Time:** 2h

### M58. Implement Dead-Letter-Topic Handling Utility
- **Objective:** A shared consumer-wrapper utility that routes a message to a `.dlq` topic after N failed processing retries (§10.5).
- **Files:** `libs/service-template/src/kafka/consumer-with-dlq.ts`.
- **Tests:** A consumer configured to always throw — verify the message lands in the DLQ topic after the configured retry count, not before.
- **Expected Output:** After 3 simulated failures, the message appears on `<topic>.dlq`.
- **Acceptance Criteria:** Retry count configurable; DLQ depth is a monitorable metric (stub metric emission, full observability wiring in Phase 13).
- **Dependencies:** M57.
- **Risk:** Medium — a missing DLQ path is how safety-relevant events silently vanish.
- **Estimated Time:** 2h

---

## Phase 4 — Sensor Simulator & Ingestion (M59-M64)
Implements `ARCHITECTURE.md` §17.4's physics-informed simulator, the concrete data source every later phase demos against.

### M59. Build the Baseline Sensor Simulator
- **Objective:** A generator producing realistic noisy baseline time series (pressure, temperature, vibration, gas) per sensor type, matching each type's normal operating range from `sensor_types`.
- **Files:** `libs/sim-data/src/baseline-generator.ts`.
- **Tests:** Statistical test confirming generated values stay within the configured `min_range`/`max_range` band with realistic noise distribution (not flat-line, not wildly erratic).
- **Expected Output:** A 10-minute simulated run plotted shows plausible sensor noise, not a straight line or random walk.
- **Acceptance Criteria:** Output visually and statistically plausible for at least pressure, temperature, and vibration sensor types.
- **Dependencies:** M18, M12 (sensor_types).
- **Risk:** Low.
- **Estimated Time:** 3h

### M60. Add Failure-Injection Scenarios to the Simulator
- **Objective:** Scripted drift/spike/failure patterns (the "Predicted Leak" demo scenario from `ARCHITECTURE.md` §5.1 — gradual pressure/thermal drift on a specific equipment tag).
- **Files:** `libs/sim-data/src/scenarios/predicted-leak.scenario.ts`.
- **Tests:** Run the scenario; verify the generated pressure signal shows the specified drift rate (+0.3%/min) at the specified time offset.
- **Expected Output:** The scenario, when plotted, visually matches the drift pattern described in `ARCHITECTURE.md` §5.1.
- **Acceptance Criteria:** Scenario is deterministic given a fixed seed (repeatable for demo purposes) and parameterized (equipment tag, start time, drift rate all configurable).
- **Dependencies:** M59.
- **Risk:** Low.
- **Estimated Time:** 2h

### M61. Build the MQTT Protocol Adapter
- **Objective:** The Ingestion Gateway adapter (§17.2) normalizing MQTT-published readings into the canonical `telemetry.raw` schema (M55).
- **Files:** `services/ingestion-gateway/src/adapters/mqtt.adapter.ts`.
- **Tests:** Publish a raw MQTT message; verify it lands on `telemetry.raw` in the canonical schema shape, quality-flagged `good`.
- **Expected Output:** A message published to a local MQTT broker appears, transformed, on the Kafka topic.
- **Acceptance Criteria:** Schema transformation verified against M55's schema validator.
- **Dependencies:** M55, M51.
- **Risk:** Medium — this is the actual OT-to-IT boundary crossing point (`ARCHITECTURE.md` §24.2).
- **Estimated Time:** 3h

### M62. Build an OPC-UA Adapter Stub
- **Objective:** A second protocol adapter proving the "protocol-agnostic beyond the adapter layer" claim (§17.2) — a minimal stub is sufficient to prove the pattern, full OPC-UA client library integration can follow later.
- **Files:** `services/ingestion-gateway/src/adapters/opcua.adapter.ts`.
- **Tests:** A stub OPC-UA source produces a reading; verify it lands on `telemetry.raw` in the identical canonical shape M61 produces.
- **Expected Output:** Both adapters' output is schema-identical and indistinguishable to any downstream consumer.
- **Acceptance Criteria:** No downstream code changes were needed to add this second adapter — proving the abstraction actually holds.
- **Dependencies:** M61.
- **Risk:** Low.
- **Estimated Time:** 2h

### M63. Wire Simulator → Adapter → `telemetry.raw` → `sensor_readings`
- **Objective:** The first full, live, end-to-end data path: simulated sensor → MQTT → adapter → Kafka → a consumer writing into the `sensor_readings` hypertable.
- **Files:** `services/ingestion-gateway/src/consumers/telemetry-persister.consumer.ts`.
- **Tests:** Run the M60 scenario; query `sensor_readings` after a fixed duration and confirm the row count and value ranges match what the simulator emitted.
- **Expected Output:** `SELECT count(*), min(value), max(value) FROM sensor_readings WHERE sensor_id = X` matches the simulator's known output for that window.
- **Acceptance Criteria:** Zero data loss across the full path over a 10-minute run at the sensor's configured sample rate.
- **Dependencies:** M60, M61, M38.
- **Risk:** Medium — first true end-to-end path; a bug anywhere in the chain shows up here.
- **Estimated Time:** 3h

### M64. Add Data-Quality Flagging to Ingestion
- **Objective:** Detect and flag out-of-range or stale readings as `quality = 'uncertain'`/`'bad'` at the adapter layer (§17.2).
- **Files:** `services/ingestion-gateway/src/domain/quality-flag.service.ts`.
- **Tests:** Feed an out-of-range value through the pipeline; verify it lands in `sensor_readings` flagged `bad`, not silently accepted as `good`.
- **Expected Output:** A deliberately out-of-range test reading is correctly flagged.
- **Acceptance Criteria:** Flagging logic runs at ingestion time, before the row is ever persisted — not as a later batch job.
- **Dependencies:** M63.
- **Risk:** Low.
- **Estimated Time:** 2h

---

## Phase 5 — Knowledge Graph (M65-M74)
Implements `KNOWLEDGE_GRAPH.md`. Knowledge Agent (`services/rag-service` or a dedicated `services/knowledge-graph/`) is the sole writer, per that document's single-writer discipline.

### M65. Verify Neo4j Constraints and Indexes
- **Objective:** Apply `KNOWLEDGE_GRAPH.md` §4's full constraint/index script.
- **Files:** `services/knowledge-graph/migrations/001_constraints.cypher`.
- **Tests:** Attempt to create two nodes with the same `id` for a constrained label — second must fail.
- **Expected Output:** `SHOW CONSTRAINTS` lists all 13 uniqueness constraints; duplicate-id insert fails.
- **Acceptance Criteria:** Every constraint from §4 present and individually verified to reject a duplicate.
- **Dependencies:** M5.
- **Risk:** Low.
- **Estimated Time:** 2h

### M66. Build the CDC Consumer Skeleton (Kafka → Neo4j)
- **Objective:** A consumer service subscribing to `equipment.*` events, applying `MERGE` writes (§7's sync strategy) — proving the pattern before wiring every node type.
- **Files:** `services/knowledge-graph/src/consumers/equipment-sync.consumer.ts`.
- **Tests:** Publish a synthetic `equipment.created` event; verify the corresponding node appears in Neo4j with matching `id`.
- **Expected Output:** A Cypher query for the test equipment's `id` returns the expected node.
- **Acceptance Criteria:** `MERGE`-based idempotency verified: publishing the same event twice does not create a duplicate node.
- **Dependencies:** M65, M57.
- **Risk:** Medium — this pattern is reused for every other node type; worth getting right once.
- **Estimated Time:** 3h

### M67. Implement Building/Zone/Equipment Node Sync
- **Objective:** Extend M66's pattern to all three node types plus their `HAS_BUILDING`/`HAS_ZONE`/`CONTAINS` relationships (§5.2's Cypher).
- **Files:** `services/knowledge-graph/src/consumers/topology-sync.consumer.ts`.
- **Tests:** Run M43's seed data through the sync consumer (via a backfill script); verify the full 3-building, 10-zone, 40-equipment topology matches Postgres exactly.
- **Expected Output:** `MATCH (z:Zone) RETURN count(z)` returns 10; spot-check 3 equipment nodes' zone parentage.
- **Acceptance Criteria:** Full seed-data topology reconciled 1:1 between Postgres and Neo4j.
- **Dependencies:** M66, M43.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M68. Implement Sensor Node + `MONITORS` Relationship Sync
- **Objective:** §2.2/§3.2's sensor sync pattern.
- **Files:** `services/knowledge-graph/src/consumers/sensor-sync.consumer.ts`.
- **Tests:** Verify a sensor node links to the correct equipment via `MONITORS`, and an ambient sensor links to its zone via `MONITORS_AMBIENT`.
- **Expected Output:** Both relationship types independently verified with at least one example each.
- **Acceptance Criteria:** Matches the seed data's 100 sensors exactly.
- **Dependencies:** M67, M18.
- **Risk:** Low.
- **Estimated Time:** 2h

### M69. Seed `FLOWS_TO` Process Topology
- **Objective:** Populate the physical flow-topology relationships (§3.2) for the seed dataset — this is authored/configured data (real plant topology), not derived from an event stream, so this milestone is a one-time seeding script rather than a live consumer.
- **Files:** `services/knowledge-graph/scripts/seed-flow-topology.cypher`.
- **Tests:** Run `KNOWLEDGE_GRAPH.md` §6.1's downstream-impact query against the seeded topology; verify it returns a sensible multi-hop chain.
- **Expected Output:** The variable-depth query from §6.1 returns equipment at 1, 2, and 3 hops downstream of a chosen valve.
- **Acceptance Criteria:** At least one realistic multi-branch topology (not purely linear) exists in the seed data, to genuinely exercise the graph's advantage over a linear chain.
- **Dependencies:** M67.
- **Risk:** Low.
- **Estimated Time:** 2h

### M70. Implement Worker/Permit Node Sync
- **Objective:** §2.3's `Worker`/`Permit` sync plus `ASSIGNED_TO`, `HOLDS`, `AUTHORIZES_WORK_ON`, `SCOPED_TO` relationships.
- **Files:** `services/knowledge-graph/src/consumers/worker-permit-sync.consumer.ts`.
- **Tests:** Verify a seeded permit's `AUTHORIZES_WORK_ON` correctly resolves to its equipment; run §6.4's permit-conflict-check query and confirm correct results.
- **Expected Output:** §6.4's Cypher query returns the expected active permit for a test equipment ID.
- **Acceptance Criteria:** Permit Agent's future conflict-check dependency (Phase 7) is provably satisfiable by this milestone's output alone.
- **Dependencies:** M67, M23, M20.
- **Risk:** Low.
- **Estimated Time:** 2h

### M71. Implement Incident Node Sync (Without `SIMILAR_TO` Yet)
- **Objective:** §2.4's `Incident` node sync plus `OCCURRED_IN`/`INVOLVED_EQUIPMENT` — `SIMILAR_TO` deferred to M72 since it requires embedding similarity, not just event sync.
- **Files:** `services/knowledge-graph/src/consumers/incident-sync.consumer.ts`.
- **Tests:** Create a test incident via Incident Service (M52); verify the corresponding graph node and relationships appear within a few seconds.
- **Expected Output:** A newly-created incident is queryable in Neo4j almost immediately after creation via the API.
- **Acceptance Criteria:** End-to-end latency from `POST /incidents` to graph node existence measured and under 5 seconds.
- **Dependencies:** M67, M52.
- **Risk:** Low.
- **Estimated Time:** 2h

### M72. Implement `SIMILAR_TO` Incident Similarity Computation
- **Objective:** A periodic batch job computing embedding-based incident similarity and writing `SIMILAR_TO {score}` edges (§3.2).
- **Files:** `services/knowledge-graph/src/jobs/incident-similarity.job.ts`.
- **Tests:** Seed two deliberately similar test incidents (same equipment type, similar root cause text) and two dissimilar ones; verify the job links the similar pair with a high score and does not link the dissimilar ones.
- **Expected Output:** `MATCH (:Incident)-[r:SIMILAR_TO]->(:Incident) RETURN r.score` shows a high score for the known-similar pair only.
- **Acceptance Criteria:** Job is idempotent (safe to re-run) and scoped to avoid an all-pairs comparison blowing up at scale (documented limitation, acceptable for hackathon scope).
- **Dependencies:** M71.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M73. Write Integration Test: Downstream Impact Traversal
- **Objective:** Automate §6.1's Cypher query as a CI-runnable test against the seeded topology from M69.
- **Files:** `services/knowledge-graph/tests/downstream-impact.test.ts`.
- **Tests:** The query itself, asserting exact expected equipment tags at each hop depth.
- **Expected Output:** Test passes against the known seed topology; fails if topology seeding regresses.
- **Acceptance Criteria:** Test is deterministic and tied to the fixed seed data, not live/mutable state.
- **Dependencies:** M69.
- **Risk:** Low.
- **Estimated Time:** 1h

### M74. Write Integration Test: Graph-Constrained Candidate Generation
- **Objective:** Automate §6.2's Cypher query — the single highest-frequency query the Risk Fusion Agent will depend on in Phase 7.
- **Files:** `services/knowledge-graph/tests/graph-constrained-candidates.test.ts`.
- **Tests:** For a known seeded equipment ID, assert the exact expected set of admitted sensors, active permits, and historical incidents.
- **Expected Output:** Test passes, proving this query is ready to be depended on before Phase 7 builds against it.
- **Acceptance Criteria:** This test existing and passing is a hard prerequisite gate before M95 (Risk Fusion Agent's Core) begins.
- **Dependencies:** M68, M70, M71.
- **Risk:** Medium — everything the Risk Fusion Engine does depends on this query being correct.
- **Estimated Time:** 2h

---

## Phase 6 — RAG System (M75-M86)
Implements `RAG_SYSTEM.md`.

### M75. Stand Up the Vector Store (pgvector)
- **Objective:** Enable `pgvector` on a dedicated schema/database, per `ARCHITECTURE.md` §12.1's hackathon-scope choice.
- **Files:** `services/rag-service/migrations/001_pgvector.sql`.
- **Tests:** Insert a test vector; run a cosine-similarity query; verify expected nearest-neighbor ordering on 3 known test vectors.
- **Expected Output:** A hand-constructed 3-vector similarity test returns the mathematically correct ranking.
- **Acceptance Criteria:** Extension enabled; basic similarity search mathematically verified.
- **Dependencies:** M4.
- **Risk:** Low.
- **Estimated Time:** 2h

### M76. Build the Document Ingestion Pipeline Skeleton
- **Objective:** A PDF/text parser producing layout-aware structured output (headings, clause numbers preserved) per `RAG_SYSTEM.md` §2.2.
- **Files:** `services/rag-service/src/ingestion/document-parser.ts`.
- **Tests:** Parse a sample SOP PDF and a sample regulation excerpt; verify heading hierarchy and clause numbering are preserved as structured metadata, not flattened into plain text.
- **Expected Output:** Parsed output for a test regulation shows `section_reference: "Section 87(2)"` correctly extracted.
- **Acceptance Criteria:** Both a well-structured internal SOP and a denser regulatory PDF parse correctly.
- **Dependencies:** M75.
- **Risk:** Medium — parsing quality determines every downstream stage's quality.
- **Estimated Time:** 3h

### M77. Implement Chunking Strategy — SOPs and Manuals
- **Objective:** §3.2's step-bounded chunking for Safety SOPs and section/table-bounded chunking for Equipment/Maintenance Manuals.
- **Files:** `services/rag-service/src/ingestion/chunkers/procedural-chunker.ts`.
- **Tests:** Chunk a sample multi-step SOP; verify no chunk spans two numbered steps and a sample manual's spec table is never split mid-row.
- **Expected Output:** Each output chunk corresponds to exactly one procedural step or one intact table.
- **Acceptance Criteria:** Table-splitting explicitly tested against a multi-row spec table to confirm atomicity.
- **Dependencies:** M76.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M78. Implement Chunking Strategy — Regulations
- **Objective:** §3.2's clause-bounded chunking for Factory Act/DGMS/OISD text, with zero overlap.
- **Files:** `services/rag-service/src/ingestion/chunkers/regulatory-chunker.ts`.
- **Tests:** Chunk a sample multi-clause regulatory excerpt; verify each chunk is exactly one clause, never split, never overlapping an adjacent clause.
- **Expected Output:** A 5-clause test document produces exactly 5 chunks.
- **Acceptance Criteria:** Zero-overlap policy verified explicitly (a common temptation to "just add a little overlap everywhere" must be resisted here specifically).
- **Dependencies:** M76.
- **Risk:** Low.
- **Estimated Time:** 2h

### M79. Implement Chunking Strategy — Incident/Audit/Inspection Records
- **Objective:** §3.2's section-bounded chunking for Incident Reports/Near Misses and finding-bounded chunking for Audit/Inspection Reports, with structured fields (severity, dates) extracted to metadata rather than embedded as prose (§3.3).
- **Files:** `services/rag-service/src/ingestion/chunkers/record-chunker.ts`.
- **Tests:** Chunk a test incident record; verify `severity`/`equipment_id` appear only in chunk metadata, never duplicated into the embedded text.
- **Expected Output:** The chunk's `normalized_value`/text content excludes the structured fields verified present in `ChunkMetadata`.
- **Acceptance Criteria:** §3.3's "never re-embed structured fields as prose" rule verified, not just described.
- **Dependencies:** M76.
- **Risk:** Low.
- **Estimated Time:** 2h

### M80. Implement Embedding Generation and Storage
- **Objective:** Wire a domain-adapted embedding model (§4.1) generating and storing vectors for every chunk from M77-M79.
- **Files:** `services/rag-service/src/embedding/embed-chunk.service.ts`.
- **Tests:** Embed a known chunk twice; verify identical output (determinism); embed two semantically similar chunks and confirm high cosine similarity.
- **Expected Output:** Similarity score between two paraphrased test sentences is measurably higher than between two unrelated ones.
- **Acceptance Criteria:** `gate_structure_version`-equivalent embedding-model version tag (§4.3) stored alongside every vector from day one, even before any re-embedding event ever occurs.
- **Dependencies:** M75, M77, M78, M79.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M81. Implement Keyword/BM25 Search
- **Objective:** §5.2's exact-match retrieval path using Postgres full-text search, for clause numbers/part numbers vector search handles poorly.
- **Files:** `services/rag-service/src/retrieval/keyword-search.service.ts`.
- **Tests:** Query for an exact clause number ("Cl. 4.3"); verify it's returned even when a semantically-similar-but-differently-numbered clause exists in the corpus.
- **Expected Output:** Exact clause-number query returns the precise match, not a semantically-close decoy.
- **Acceptance Criteria:** This is explicitly tested against a decoy case designed to fool pure vector search.
- **Dependencies:** M80.
- **Risk:** Low.
- **Estimated Time:** 2h

### M82. Implement Hybrid Search Fusion (Reciprocal Rank Fusion)
- **Objective:** §5.1/§5.3's fusion of vector, keyword, and (stubbed for now) graph-scoped signals into one ranked candidate list.
- **Files:** `services/rag-service/src/retrieval/hybrid-search.service.ts`.
- **Tests:** A query that only a keyword search would surface, and one that only vector search would surface, both appear in the fused top-K.
- **Expected Output:** Both single-modality-dependent test queries return correct results after fusion.
- **Acceptance Criteria:** Fusion doesn't let either signal dominate to the point of excluding the other's unique strengths.
- **Dependencies:** M81, M74 (graph-scoped signal depends on the Knowledge Graph query being ready).
- **Risk:** Medium.
- **Estimated Time:** 3h

### M83. Implement Cross-Encoder Re-Ranking
- **Objective:** §7.1's second-pass re-ranker over the top-K fused candidates.
- **Files:** `services/rag-service/src/retrieval/reranker.service.ts`.
- **Tests:** A candidate set where the correct answer is ranked 3rd by hybrid search must move to rank 1 after re-ranking, on a hand-constructed test case designed to expose bi-encoder limitations.
- **Expected Output:** Re-ranked order differs from and improves on the pre-rerank order for the constructed test case.
- **Acceptance Criteria:** Graph-aware boost (§7.2) and diversity penalty (§7.3) both independently verified with dedicated test cases.
- **Dependencies:** M82.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M84. Implement Citation Formatting
- **Objective:** §8.1's class-specific citation rendering (statutory format for regulations, `SOP-####, vN` format for internal docs).
- **Files:** `services/rag-service/src/citation/citation-formatter.service.ts`.
- **Tests:** Format a citation for each of the 10 document classes; verify each matches its exact template from §8.1's table.
- **Expected Output:** All 10 example citations from the table render exactly as specified.
- **Acceptance Criteria:** No generic `[source N]` fallback used anywhere a class-specific template exists.
- **Dependencies:** M83.
- **Risk:** Low.
- **Estimated Time:** 2h

### M85. Implement Citation Verification (Entailment Check)
- **Objective:** §8.3's post-generation existence + NLI-entailment verification pass, and §8.4's stricter numeric-claim matching.
- **Files:** `services/rag-service/src/citation/citation-verifier.service.ts`.
- **Tests:** A generated claim that accurately reflects its cited chunk passes; a claim that cites a real chunk but overstates its content fails; a claim with a paraphrased/wrong number fails even if semantically close.
- **Expected Output:** All 3 test cases produce the correct pass/fail verdict.
- **Acceptance Criteria:** The numeric-mismatch case specifically constructed and confirmed to fail (this is the subtlest and most safety-relevant check in the whole pipeline).
- **Dependencies:** M84.
- **Risk:** High — this is the hallucination-prevention backstop the whole system's trust claim rests on.
- **Estimated Time:** 3h

### M86. Seed the RAG Corpus and Write an End-to-End Test
- **Objective:** Ingest 5 sample SOPs, 3 regulation excerpts (Factory Act/DGMS/OISD), 2 equipment manuals, and a handful of seeded incident/audit records; write one full-pipeline test.
- **Files:** `services/rag-service/scripts/seed-corpus.ts`, `services/rag-service/tests/e2e-grounded-query.test.ts`.
- **Tests:** Ask a known question with a known correct answer in the seeded corpus; verify the returned answer cites the correct source and passes verification; ask an unanswerable question and verify explicit refusal (§9's layer 4).
- **Expected Output:** Both the answerable and the deliberately-unanswerable test query produce the correct respective behavior.
- **Acceptance Criteria:** This is the first milestone where the full RAG pipeline (M75-M85) is proven working end to end, not just stage by stage.
- **Dependencies:** M75-M85 (all of Phase 6).
- **Risk:** Medium.
- **Estimated Time:** 3h

---

## Phase 7 — Agent Fleet (M87-M110)
Implements `AGENT_ARCHITECTURE.md` and `RISK_FUSION_ENGINE.md`. Each agent's Core is built first (the deterministic/statistical part); the Reasoning Shell (LLM-mediated, per `AGENT_ARCHITECTURE.md` §0.1) is added only where that document specified it has a real role — several agents deliberately get no Shell milestone at all, matching the doc's own restraint.

### M87. Implement Sensor Agent Core (Statistical Ensemble)
- **Objective:** `AGENT_ARCHITECTURE.md` §1's EWMA + isolation-forest ensemble, consuming `sensor_readings`.
- **Files:** `services/anomaly-detection/src/core/statistical-ensemble.ts`.
- **Tests:** Feed M60's known drift scenario through the ensemble; verify it flags an anomaly at approximately the expected time offset, and does not flag the stable baseline period.
- **Expected Output:** Anomaly flag timestamp falls within an acceptable window of the scenario's known drift onset.
- **Acceptance Criteria:** Zero false positives on 30 minutes of pure baseline noise from M59.
- **Dependencies:** M63, M60.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M88. Implement Sensor Agent Assertion Publishing
- **Objective:** Publish `agent.assertion` messages (envelope per `AGENT_ARCHITECTURE.md` §0.3) onto `anomaly.detected` when M87's ensemble crosses threshold.
- **Files:** `services/anomaly-detection/src/publishers/assertion-publisher.ts`.
- **Tests:** Verify a published assertion's `evidence_refs` correctly points back to the specific `sensor_readings` rows that triggered it.
- **Expected Output:** A consumed test message's `evidence_refs` resolves to real, existing rows.
- **Acceptance Criteria:** `evidence_refs` non-empty on every assertion, per the doc's non-negotiable rule.
- **Dependencies:** M87, M55.
- **Risk:** Low.
- **Estimated Time:** 2h

### M89. Implement Vision Agent Core (Mock CV Inference)
- **Objective:** `AGENT_ARCHITECTURE.md` §2's per-capability detectors, using a small pre-trained/mock model against static test images (real fine-tuning deferred — hackathon scope per `ARCHITECTURE.md` §18.4).
- **Files:** `services/computer-vision/src/core/detectors/thermal-anomaly.detector.ts`.
- **Tests:** Run against a known test image set (some containing a synthetic hotspot, some not); verify correct classification.
- **Expected Output:** Detector correctly distinguishes the hotspot images from the clean ones.
- **Acceptance Criteria:** At least one detector (thermal) working end to end against test fixtures before adding others.
- **Dependencies:** M32.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M90. Implement Vision Agent Temporal Smoothing Gate
- **Objective:** §18.2/`AGENT_ARCHITECTURE.md` §2's mandatory N-consecutive-frame persistence check before any event emission.
- **Files:** `services/computer-vision/src/core/temporal-smoothing.service.ts`.
- **Tests:** A single-frame false-positive spike must NOT emit an event; the same detection sustained across N frames must emit exactly one event, not N events.
- **Expected Output:** Both cases produce the correct, distinct behavior.
- **Acceptance Criteria:** This is the primary defense against alert-fatigue false positives — verified with an explicit single-frame-spike test case, not assumed.
- **Dependencies:** M89.
- **Risk:** Medium.
- **Estimated Time:** 2h

### M91. Implement Worker Agent Core (Badge + CV Fusion)
- **Objective:** `AGENT_ARCHITECTURE.md` §3's identity/position reconciliation logic, including the explicit discrepancy-flagging (never-silently-resolve) behavior.
- **Files:** `services/predictive-risk-engine/src/agents/worker-agent/fusion.service.ts` (or a dedicated `services/worker-agent/`).
- **Tests:** A matched badge+CV case produces a single confident location; a mismatched-count case produces an explicit discrepancy flag, not a silently-picked "winner."
- **Expected Output:** The mismatch test case's output includes both source counts and a discrepancy flag, never just one number.
- **Acceptance Criteria:** Identity-confidence and location-confidence reported as two distinct values, never merged.
- **Dependencies:** M90, M20.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M92. Implement Permit Agent Conflict-Check Query
- **Objective:** `AGENT_ARCHITECTURE.md` §4's fail-closed synchronous conflict-check, wired to `KNOWLEDGE_GRAPH.md` §6.4's Cypher.
- **Files:** `services/incident-service/src/agents/permit-agent/conflict-check.service.ts`.
- **Tests:** A request against equipment with an active permit returns a conflict; against equipment with none returns clear; the Neo4j connection is deliberately killed mid-test to verify the fail-closed (not fail-open) behavior.
- **Expected Output:** All three cases — conflict, clear, and connection-failure — produce the documented distinct outcomes.
- **Acceptance Criteria:** The fail-closed behavior under simulated Neo4j outage is the most important assertion in this test and must be explicitly present, not incidental.
- **Dependencies:** M70, M74.
- **Risk:** High — a fail-open bug here is a real safety hazard per the doc's own reasoning.
- **Estimated Time:** 2h

### M93. Implement Maintenance Agent Work-Order Creation
- **Objective:** `AGENT_ARCHITECTURE.md` §5's priority-queue scheduling and idempotent (`prediction_id`-keyed) work-order creation.
- **Files:** `services/predictive-risk-engine/src/agents/maintenance-agent/work-order.service.ts`.
- **Tests:** Publish the same triggering prediction event twice; verify only one `maintenance_records` row is created, not two.
- **Expected Output:** Idempotency confirmed via duplicate-event replay.
- **Acceptance Criteria:** Priority ordering correctly reflects criticality × urgency on a multi-candidate test set.
- **Dependencies:** M29, M24.
- **Risk:** Low.
- **Estimated Time:** 2h

### M94. Implement Knowledge Agent RAG Query Wrapper
- **Objective:** `AGENT_ARCHITECTURE.md` §6's agent-facing interface over the Phase 6 RAG pipeline, adding the Agent Bus envelope on top of raw RAG output.
- **Files:** `services/rag-service/src/agents/knowledge-agent/query-wrapper.service.ts`.
- **Tests:** A query from another agent (simulated) receives a properly-enveloped response including `confidence` and `evidence_refs`.
- **Expected Output:** Response shape matches the Agent Bus standard from `AGENT_ARCHITECTURE.md` §0.3, not just raw RAG service output.
- **Acceptance Criteria:** This wrapper is what every other agent in this phase actually calls — verified by at least one real cross-agent call in a later milestone (M110).
- **Dependencies:** M86.
- **Risk:** Low.
- **Estimated Time:** 2h

### M95. Implement Risk Fusion Agent Core — Graph-Constrained Candidate Generation
- **Objective:** `RISK_FUSION_ENGINE.md` §3.2, wired to `KNOWLEDGE_GRAPH.md` §6.2's already-tested query (M74).
- **Files:** `services/predictive-risk-engine/src/risk-fusion/candidate-generation.service.ts`.
- **Tests:** For a known seeded equipment, verify the exact admitted-evidence set matches M74's already-verified expectations.
- **Expected Output:** Identical result to the M74 test, now called from within the Risk Fusion Agent rather than as a standalone query.
- **Acceptance Criteria:** Zero divergence from M74's already-proven behavior — this milestone is integration, not re-verification from scratch.
- **Dependencies:** M74.
- **Risk:** Low.
- **Estimated Time:** 2h

### M96. Implement Bayesian Fusion — Gas Leak Network
- **Objective:** `RISK_FUSION_ENGINE.md` §4.3's noisy-OR network over gas/pressure/flow/vision/equipment-health evidence.
- **Files:** `services/predictive-risk-engine/src/risk-fusion/networks/gas-leak.network.ts`.
- **Tests:** Reproduce §5's worked-example arithmetic exactly (feed the documented evidence sequence, verify the posterior matches the documented odds-multiplication result to within rounding).
- **Expected Output:** Computed posterior matches the worked example's numbers.
- **Acceptance Criteria:** The specific documented worked example is the literal test fixture — not a new, undocumented test case.
- **Dependencies:** M95.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M97. Implement Bayesian Fusion — Fire Network
- **Objective:** §4.1's noisy-OR network across the three independent ignition pathways.
- **Files:** `services/predictive-risk-engine/src/risk-fusion/networks/fire.network.ts`.
- **Tests:** A test case with strong evidence on exactly one pathway (electrical fault) and none on the others must still produce a meaningfully elevated posterior, proving the disjunctive (not conjunctive) structure.
- **Expected Output:** Single-pathway evidence alone elevates the posterior, unlike the Explosion network's conjunctive requirement (M98).
- **Acceptance Criteria:** This single-pathway-sufficiency behavior is the specific thing under test, distinguishing this network's gate type from Explosion's.
- **Dependencies:** M95.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M98. Implement Bayesian Fusion — Explosion Network (Noisy-AND Gate)
- **Objective:** §4.2's conjunctive Fuel-in-Range/Ignition-Source/Confinement structure — the network where "no simple IF-statements" is most load-bearing.
- **Files:** `services/predictive-risk-engine/src/risk-fusion/networks/explosion.network.ts`.
- **Tests:** Strong evidence on two of three sub-conditions with zero evidence on the third must produce a *capped*, not maximal, posterior — proving the noisy-AND behaves as a graded joint condition, not a boolean AND that would zero out entirely on missing evidence, nor a noisy-OR that would let two strong signals alone reach a high score.
- **Expected Output:** Two-of-three-strong test case produces a posterior meaningfully below what all-three-strong would produce, and meaningfully above what one-of-three-strong would produce.
- **Acceptance Criteria:** §5's full worked example reproduced exactly, matching the 87.8% figure to within rounding.
- **Dependencies:** M95, M96 (Gas Leak feeds forward per §4.6).
- **Risk:** High — this is the single most technically demanding milestone in the fleet and the one most likely to be gotten subtly wrong.
- **Estimated Time:** 3h

### M99. Implement Bayesian Fusion — Worker Injury Network
- **Objective:** §4.4's multiplicative hazard×exposure structure, taking Fire/Explosion/Gas Leak posteriors as upstream inputs.
- **Files:** `services/predictive-risk-engine/src/risk-fusion/networks/worker-injury.network.ts`.
- **Tests:** Verify a worker present in a zone with a high Explosion posterior produces a materially higher Worker Injury score than the same Explosion posterior with no worker present.
- **Expected Output:** The two test cases (worker present vs. absent, identical hazard posterior) produce meaningfully different Worker Injury scores.
- **Acceptance Criteria:** Confirms the multiplicative (not merely additive) interaction structure the doc specifies.
- **Dependencies:** M96, M97, M98, M91.
- **Risk:** Medium.
- **Estimated Time:** 2h

### M100. Implement Bayesian Fusion — Machine Failure Network
- **Objective:** §4.5's temporally-dominated network, weighted toward `machine_state_history` trend/precursor-similarity features over instantaneous readings.
- **Files:** `services/predictive-risk-engine/src/risk-fusion/networks/machine-failure.network.ts`.
- **Tests:** A machine with a rising-but-still-nominal vibration trend must score higher than one with an identical instantaneous vibration value but a flat historical trend.
- **Expected Output:** The trend-aware case outscores the flat-trend case despite identical current readings — proving temporal features, not just instantaneous values, drive the score.
- **Acceptance Criteria:** This is the network most dependent on §3.3's temporal reasoning layer (M101) rather than instantaneous Bayesian fusion alone.
- **Dependencies:** M95, M39.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M101. Implement Temporal Reasoning Layer
- **Objective:** `RISK_FUSION_ENGINE.md` §3.3's rate-of-change, persistence, lead-lag cross-correlation, and precursor-sequence-similarity feature extraction, feeding all five networks above.
- **Files:** `services/predictive-risk-engine/src/risk-fusion/temporal-features.service.ts`.
- **Tests:** A synthetic pair of signals with a known, deliberately-injected 90-second lead-lag relationship must be correctly detected by the cross-correlation feature.
- **Expected Output:** Detected lag matches the injected 90-second offset within a small tolerance.
- **Acceptance Criteria:** All four feature types (rate-of-change, persistence, lead-lag, precursor-similarity) individually unit-tested.
- **Dependencies:** M63.
- **Risk:** Medium.
- **Note:** Built here, referenced by M96-M100 — represents the shared dependency those milestones actually rely on for their trend-sensitive test cases.
- **Estimated Time:** 3h

### M102. Implement Confidence Estimation (Epistemic/Aleatoric Split)
- **Objective:** §3.5/§6's structured confidence object, including the degraded-sensor-quality scenario from §6's worked example.
- **Files:** `services/predictive-risk-engine/src/risk-fusion/confidence-estimator.service.ts`.
- **Tests:** Re-run M98's Explosion test case with the dominant sensor's `quality` flagged `uncertain`; verify `epistemic_flag` shifts to `"elevated"` and the confidence band widens, while the posterior itself may remain similar.
- **Expected Output:** Identical evidence values but degraded quality flag produce a materially different confidence object, not just a wider generic error bar.
- **Acceptance Criteria:** Epistemic and aleatoric uncertainty are verified as genuinely separate fields responding to genuinely different test conditions (missing/degraded data vs. normal process noise).
- **Dependencies:** M98.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M103. Implement Evidence Bundle Generation
- **Objective:** `RISK_FUSION_ENGINE.md` §7's Evidence Bundle assembly — contributing-factor ranking and counterfactual generation.
- **Files:** `services/predictive-risk-engine/src/risk-fusion/evidence-bundle.service.ts`.
- **Tests:** Reproduce §5's exact counterfactual ("removing the gas evidence drops probability to ~15.3%") from the same worked-example fixture used in M96/M98.
- **Expected Output:** Computed counterfactual matches the documented figure.
- **Acceptance Criteria:** Contributing-factor ranking order matches the documented order (Gas > Pressure > Thermal > Maintenance) exactly.
- **Dependencies:** M98, M102.
- **Risk:** Low.
- **Estimated Time:** 2h

### M104. Implement Prediction Agent Survival Scoring
- **Objective:** `AGENT_ARCHITECTURE.md` §8's time-to-event model, consuming Risk Fusion Agent's posterior + `RISK_FUSION_ENGINE.md` §3.3's temporal trend features.
- **Files:** `services/predictive-risk-engine/src/agents/prediction-agent/survival-model.service.ts`.
- **Tests:** Feed the M60 drift scenario's full evidence trajectory; verify a time-to-event window is produced and that it narrows in width as more evidence accumulates over the scenario's timeline.
- **Expected Output:** A `risk_scores` row is written with a populated, narrowing time-to-event window as the scenario progresses.
- **Acceptance Criteria:** This is the first milestone writing to `risk_scores` from the live agent pipeline rather than a test insert.
- **Dependencies:** M98, M101, M27.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M105. Implement Emergency Agent Playbook Matcher
- **Objective:** `AGENT_ARCHITECTURE.md` §9's structured-criteria playbook matching (hazard class, equipment type, zone occupancy) — never free-form LLM matching for this step.
- **Files:** `services/agentic-orchestrator/src/agents/emergency-agent/playbook-matcher.service.ts`.
- **Tests:** A risk assessment matching a seeded playbook's hazard class returns that playbook; one matching nothing returns the explicit "no matching playbook" result, not a forced best-guess.
- **Expected Output:** Both the match and no-match cases produce the correct, distinct outcome.
- **Acceptance Criteria:** The no-match path is explicitly tested — this is what feeds M105's downstream escalation-to-human behavior.
- **Dependencies:** M30, M104.
- **Risk:** Medium.
- **Estimated Time:** 2h

### M106. Implement Emergency Agent Step Sequencer + Tool-Calling
- **Objective:** §9's autonomy-tier-obedient step execution with the Step Outcome Monitor, calling M92's Permit Agent conflict-check before any gated step.
- **Files:** `services/agentic-orchestrator/src/agents/emergency-agent/step-sequencer.service.ts`.
- **Tests:** A Tier 1 step must halt and wait for an explicit approval event before proceeding — verified by asserting no side effect occurs until the approval event is published; a step whose tool call fails must halt the sequence, not proceed to the next step.
- **Expected Output:** Both the approval-gate and the failure-halt behaviors are independently, explicitly verified.
- **Acceptance Criteria:** The Tier 1 approval gate is a **structural** test (attempting to bypass it must be impossible, not merely discouraged) — matching `ARCHITECTURE.md` §19.3's guarantee.
- **Dependencies:** M105, M92, M31.
- **Risk:** High — this is the human-in-the-loop guarantee the entire product's safety claim depends on.
- **Estimated Time:** 3h

### M107. Implement Compliance Agent Rule Checker
- **Objective:** `AGENT_ARCHITECTURE.md` §10's deterministic policy evaluation against `audit_logs`/`permits`.
- **Files:** `services/audit-log/src/agents/compliance-agent/rule-checker.service.ts`.
- **Tests:** A deliberately-introduced retention-policy gap in test data must be flagged; compliant test data must produce a clean pass.
- **Expected Output:** Both cases produce the correct verdict.
- **Acceptance Criteria:** Rule evaluation is fully deterministic — running the same check twice on unchanged data produces identical results.
- **Dependencies:** M34, M42.
- **Risk:** Low.
- **Estimated Time:** 2h

### M108. Implement Learning Agent Batch Evaluation Stub
- **Objective:** `AGENT_ARCHITECTURE.md` §11's offline precision/recall/calibration-drift evaluation against `predictions.actual_outcome` — a working stub sufficient to prove the human-gated-promotion pattern, not a full retraining pipeline.
- **Files:** `services/predictive-risk-engine/src/agents/learning-agent/evaluation.job.ts`.
- **Tests:** Feed a small labeled outcome set; verify the job computes a correct precision/recall figure and produces a `model.retrain_proposed` event rather than any automatic promotion.
- **Expected Output:** No `model.promoted` event is ever emitted by this job under any test condition — only proposals.
- **Acceptance Criteria:** The never-auto-promotes guarantee is the specific, explicit thing under test.
- **Dependencies:** M29.
- **Risk:** Low.
- **Estimated Time:** 2h

### M109. Implement Supervisor Agent Arbitration Logic
- **Objective:** `AGENT_ARCHITECTURE.md` §12's conservative-precedence arbitration — a single Critical assertion is never downgraded by disagreement.
- **Files:** `services/agentic-orchestrator/src/agents/supervisor-agent/arbitration.service.ts`.
- **Tests:** Two conflicting assertions, one Critical and one Low, must never resolve to anything below Critical-level escalation; verify the fail-closed fallback (§12's tested hard-coded rule) activates correctly when this agent's own dependencies are simulated as unavailable.
- **Expected Output:** Both the normal-arbitration and the agent's-own-failure-fallback cases produce the documented conservative outcome.
- **Acceptance Criteria:** The "never average away a Critical assertion" rule is the single hard-asserted behavior in this test suite.
- **Dependencies:** M88, M104, M106.
- **Risk:** High — this is the fleet's final arbitration authority; a bug here undermines every other agent's careful escalation design.
- **Estimated Time:** 3h

### M110. Write the Agent-Fleet Integration Test: The Predicted-Leak Journey
- **Objective:** Automate `AGENT_ARCHITECTURE.md` §13's full sequence diagram as one CI-runnable end-to-end test, using M60's scenario as the trigger.
- **Files:** `services/agentic-orchestrator/tests/e2e-predicted-leak.test.ts`.
- **Tests:** Run M60's scenario from cold start; assert, in order: Sensor + Vision assertions publish, Risk Fusion Agent queries Knowledge Agent for graph context, a correlated risk assertion reaches Prediction Agent, a `risk_scores` row crosses Critical, Emergency Agent proposes a playbook, Permit Agent returns no conflict, and the sequence halts awaiting human approval (never auto-executing past the Tier 1 gate).
- **Expected Output:** Every step in `AGENT_ARCHITECTURE.md` §13's diagram is independently asserted, in the documented order, within one test run.
- **Acceptance Criteria:** This is the single test that proves the entire agent fleet is one coherent system, not twelve independently-passing unit-test suites — the same bar `AGENT_ARCHITECTURE.md`'s own closing note set for the design itself.
- **Dependencies:** M87-M109 (all of Phase 7).
- **Risk:** High — the most integration-heavy test in the whole roadmap; expect this to surface bugs from earlier phases.
- **Estimated Time:** 3h

---

## Phase 8 — Frontend Foundation (M111-M117)
Implements `UI_UX_SPECIFICATION.md` §0.2's shared design system.

### M111. Scaffold the React + TypeScript App Shell
- **Objective:** `apps/web/` — routing, theming provider, empty layout shell.
- **Files:** `apps/web/src/App.tsx`, `apps/web/src/routes/index.tsx`.
- **Tests:** A smoke test asserting the app renders without error and the router navigates between two placeholder routes.
- **Expected Output:** `npm run dev` serves a blank-but-functional shell at `localhost:3000`.
- **Acceptance Criteria:** Build succeeds; navigation between two stub routes works.
- **Dependencies:** M8, M49.
- **Risk:** Low.
- **Estimated Time:** 2h

### M112. Implement the Design Token System
- **Objective:** §0.2's color tokens (severity palette, Aegis Cyan/Indigo, dark/light neutrals), typography scale, and spacing scale as a single source-of-truth token file.
- **Files:** `libs/design-system/src/tokens/colors.ts`, `libs/design-system/src/tokens/typography.ts`.
- **Tests:** A visual-regression snapshot test of a token-swatch page (all severity colors, both themes) against a committed baseline image.
- **Expected Output:** The swatch page renders every token from §0.2's tables exactly.
- **Acceptance Criteria:** Aegis Cyan's single-purpose rule (AI-generated content only) is documented as a lint-enforced convention name (e.g., `color.ai.primary`), not a raw hex value reused ad hoc.
- **Dependencies:** M111.
- **Risk:** Low.
- **Estimated Time:** 2h

### M113. Build the Shared Component Library Skeleton
- **Objective:** `Button`, `Card`, `SeverityChip`, `RiskGauge` — the first four widgets from §7.2's shared-widget list.
- **Files:** `libs/design-system/src/components/{Button,Card,SeverityChip,RiskGauge}.tsx`.
- **Tests:** Storybook/snapshot test per component across all 5 severity states and both themes.
- **Expected Output:** A Storybook instance shows all components in all documented states.
- **Acceptance Criteria:** `SeverityChip` never renders color alone — icon + text label verified present in every snapshot, per the accessibility rule in §0.2.
- **Dependencies:** M112.
- **Risk:** Low.
- **Estimated Time:** 3h

### M114. Implement Dark/Light Theme Toggle
- **Objective:** §14's Settings-screen theme control, wired to the token system from M112.
- **Files:** `libs/design-system/src/theme/ThemeProvider.tsx`.
- **Tests:** Toggling the theme control updates every M113 component's rendered colors without a page reload.
- **Expected Output:** A live toggle demonstrably re-themes the whole component set instantly.
- **Acceptance Criteria:** Dark is confirmed the default per §0.2's "dark is canonical" rule.
- **Dependencies:** M113.
- **Risk:** Low.
- **Estimated Time:** 2h

### M115. Build the Command Palette Component
- **Objective:** §0.2's ⌘K global search/action launcher.
- **Files:** `libs/design-system/src/components/CommandPalette.tsx`.
- **Tests:** Keyboard shortcut opens/closes the palette from any route; typing filters a stub action list correctly.
- **Expected Output:** Pressing ⌘K/Ctrl+K from any page opens the palette.
- **Acceptance Criteria:** Works from every route registered in M111 without needing per-route wiring (a single global listener).
- **Dependencies:** M111.
- **Risk:** Low.
- **Estimated Time:** 2h

### M116. Build the Notification Tray Component
- **Objective:** §0.2's badge-counted notification feed, wired to M53's Notification Service.
- **Files:** `apps/web/src/components/NotificationTray.tsx`.
- **Tests:** A test notification created via the API appears in the tray within the polling/WebSocket refresh window; badge count increments correctly.
- **Expected Output:** Creating a notification via `POST` makes it visible in the UI without a manual page refresh.
- **Acceptance Criteria:** Badge count matches actual unacknowledged count exactly.
- **Dependencies:** M53, M111.
- **Risk:** Low.
- **Estimated Time:** 2h

### M117. Build the Global Status Bar Component
- **Objective:** §0.2's always-visible plant-health + connection-status strip.
- **Files:** `apps/web/src/components/GlobalStatusBar.tsx`.
- **Tests:** Simulate a Realtime Gateway disconnect; verify the status bar shows the "Reconnecting…" amber state per `UI_UX_SPECIFICATION.md` §2's error-state spec.
- **Expected Output:** The disconnect scenario produces the documented visual state, not a silent failure.
- **Acceptance Criteria:** Visible on every route, matching §0.2's "always visible" requirement.
- **Dependencies:** M50, M111.
- **Risk:** Low.
- **Estimated Time:** 2h

---

## Phase 9 — Frontend Screens (M118-M138)
Implements `UI_UX_SPECIFICATION.md` §1-15, one screen (or one major sub-view) per milestone, static shell first where a screen needs both a shell and a live-wiring pass.

### M118. Build the Login Screen (Static Layout)
- **Objective:** §1's card layout, background schematic, badge/PIN toggle — visual only, not yet wired to auth.
- **Files:** `apps/web/src/screens/Login/Login.tsx`.
- **Tests:** Visual snapshot test; toggle between email/password and badge/PIN modes renders correctly.
- **Expected Output:** Screen matches §1's described layout.
- **Acceptance Criteria:** Both entry modes render; no backend call yet.
- **Dependencies:** M113.
- **Risk:** Low.
- **Estimated Time:** 2h

### M119. Wire Login Screen to Identity Service
- **Objective:** Connect M118's form to M46's `/auth/login`.
- **Files:** `apps/web/src/screens/Login/useLogin.ts`.
- **Tests:** Correct credentials navigate to the Dashboard; incorrect credentials show the inline shake+error state from §1.
- **Expected Output:** A real login round-trip succeeds end to end through the UI.
- **Acceptance Criteria:** Error and success states both match §1's specified behavior exactly (in-button spinner, inline error, never a full-page spinner).
- **Dependencies:** M118, M46, M49.
- **Risk:** Low.
- **Estimated Time:** 2h

### M120. Build the Dashboard Screen Shell
- **Objective:** §2's widget grid layout (Plant Health Score, Risk Feed, Zone Grid, Incident Strip, Twin Mini-Viewport, Activity Timeline) with static/mock data.
- **Files:** `apps/web/src/screens/Dashboard/Dashboard.tsx`.
- **Tests:** All 6 widgets render with mock data in the documented layout positions.
- **Expected Output:** Visual match to §2's described composition.
- **Acceptance Criteria:** Skeleton/loading states (§2's spec) verified by deliberately delaying mock data.
- **Dependencies:** M113, M119.
- **Risk:** Low.
- **Estimated Time:** 3h

### M121. Wire Plant Health Score to Live Data
- **Objective:** Replace mock data with a live WebSocket subscription via M50/M157 (Realtime Gateway), including the odometer-digit count-up animation from §2.
- **Files:** `apps/web/src/screens/Dashboard/widgets/PlantHealthScore.tsx`.
- **Tests:** A simulated score change over the WebSocket updates the displayed number with the documented animation, not an instant snap.
- **Expected Output:** Live score changes animate smoothly.
- **Acceptance Criteria:** Animation respects `prefers-reduced-motion` per §0.2.
- **Dependencies:** M120, M50.
- **Risk:** Low.
- **Estimated Time:** 2h

### M122. Build the Ranked Risk Feed Widget with FLIP Reorder Animation
- **Objective:** §2's most important widget — live-updating, priority-sorted cards with the FLIP reordering animation on rank change.
- **Files:** `apps/web/src/screens/Dashboard/widgets/RiskFeed.tsx`.
- **Tests:** A simulated priority change (via test data injection) triggers a visible slide-to-new-position animation, not a jump-cut re-render.
- **Expected Output:** Reordering is smooth and traceable by eye, matching §2's stated trust-building rationale.
- **Acceptance Criteria:** New Critical items produce the documented insert-flash + toast + tray-badge triple per §2's Notifications spec.
- **Dependencies:** M121, M104 (a real `risk_scores` feed to react to).
- **Risk:** Medium.
- **Estimated Time:** 3h

### M123. Build the Incident Center List View
- **Objective:** §5's filterable/sortable list with severity chips and one-line AI summaries.
- **Files:** `apps/web/src/screens/IncidentCenter/IncidentList.tsx`.
- **Tests:** Filtering by status/severity/zone correctly narrows the list against real seeded incident data.
- **Expected Output:** Filters produce correct subsets.
- **Acceptance Criteria:** Aegis-Cyan-colored AI-authored entries visually distinct from human-authored ones, per §5's color spec.
- **Dependencies:** M52, M113.
- **Risk:** Low.
- **Estimated Time:** 3h

### M124. Build the Incident Center Detail/Timeline View
- **Objective:** §5's split-view timeline reconstructed from `incident_timeline_events`.
- **Files:** `apps/web/src/screens/IncidentCenter/IncidentDetail.tsx`.
- **Tests:** A seeded incident with multiple timeline events renders them in correct chronological order with correct actor-type color-coding.
- **Expected Output:** Timeline matches the underlying immutable event log exactly.
- **Acceptance Criteria:** The non-optimistic "Close Incident" behavior from §5 verified (UI does not show closed until server confirms).
- **Dependencies:** M123, M26.
- **Risk:** Low.
- **Estimated Time:** 3h

### M125. Build the Worker Tracking Roster View
- **Objective:** §6's roster list and zone-occupancy bar chart, respecting the ethics-scoped default view (no movement trails).
- **Files:** `apps/web/src/screens/WorkerTracking/Roster.tsx`.
- **Tests:** Occupancy bar reflects real seeded worker/zone data; verify no historical-trail data is fetched or rendered by default.
- **Expected Output:** Roster and occupancy match live data; a code/API-level check confirms no trail-history endpoint is called from this screen.
- **Acceptance Criteria:** The privacy-by-design constraint from `UI_UX_SPECIFICATION.md` §6 is verified as an actual absence of a network call, not just a UI omission.
- **Dependencies:** M91, M113.
- **Risk:** Medium — this is a privacy-sensitive screen; worth verifying rigorously.
- **Estimated Time:** 3h

### M126. Build the Machine Health Screen Shell
- **Objective:** §7's tabbed layout (Live Telemetry, Health History, Relationships, Documentation) with mock data.
- **Files:** `apps/web/src/screens/MachineHealth/MachineHealth.tsx`.
- **Tests:** All 4 tabs render and switch correctly.
- **Expected Output:** Tab navigation works; each tab shows its documented content type.
- **Acceptance Criteria:** Per-tab independent error states verified (§7's "one dependency's outage degrades one tab" principle) by simulating a failed Relationships-tab fetch alone.
- **Dependencies:** M113.
- **Risk:** Low.
- **Estimated Time:** 3h

### M127. Wire Machine Health's Live Telemetry Tab
- **Objective:** Connect the tab to real `sensor_readings`/`machine_state_history` for a selected equipment.
- **Files:** `apps/web/src/screens/MachineHealth/tabs/LiveTelemetry.tsx`.
- **Tests:** Selecting a seeded machine shows its real, live-updating sensor charts.
- **Expected Output:** Charts reflect the M63 ingestion pipeline's live output for that specific equipment.
- **Acceptance Criteria:** Clicking a chart correctly deep-links into Sensor Analytics pre-filtered, per §7's specified hub-and-spoke interaction.
- **Dependencies:** M126, M63.
- **Risk:** Low.
- **Estimated Time:** 2h

### M128. Build the Sensor Analytics Multi-Chart Workspace
- **Objective:** §8's flexible multi-pane chart workspace with signal picker and shared time-range control.
- **Files:** `apps/web/src/screens/SensorAnalytics/Workspace.tsx`.
- **Tests:** Adding two signals creates two synchronized panes; changing the shared time range updates both simultaneously.
- **Expected Output:** Multi-pane synchronization works correctly.
- **Acceptance Criteria:** "View as data table" accessibility toggle (§8) present and functional on every chart.
- **Dependencies:** M113, M40 (continuous aggregates for performant range queries).
- **Risk:** Medium.
- **Estimated Time:** 3h

### M129. Build the Risk Timeline Screen
- **Objective:** §9's observed-past/predicted-future chart with the "now" marker and incident-marker overlay.
- **Files:** `apps/web/src/screens/RiskTimeline/RiskTimeline.tsx`.
- **Tests:** For a seeded equipment with both historical `risk_scores` and at least one incident, verify the incident marker aligns correctly with the historical risk curve at its actual timestamp.
- **Expected Output:** Visual alignment between the risk curve's rise and the incident marker is correct and checkable.
- **Acceptance Criteria:** The gradient-fade "confidence decreases with forecast distance" treatment (§9) is present, not a flat-opacity forecast band.
- **Dependencies:** M104, M113.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M130. Build the Emergency Control Screen — Playbook Step Cards
- **Objective:** §10's step-by-step approve/reject/modify cards with autonomy-tier badges.
- **Files:** `apps/web/src/screens/EmergencyControl/PlaybookSteps.tsx`.
- **Tests:** For a seeded playbook execution in progress, each step renders its correct tier badge and independent approve/reject controls.
- **Expected Output:** All steps from a test emergency event render correctly, independently actionable.
- **Acceptance Criteria:** The restrained, non-decorative motion rule from §10 is verified by absence — no animation on this screen beyond functional progress indication.
- **Dependencies:** M106, M113.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M131. Wire the Press-and-Hold Confirmation Interaction
- **Objective:** §10's ~800ms press-and-hold gesture for the primary Execute action, plus its keyboard/switch-access equivalent.
- **Files:** `apps/web/src/screens/EmergencyControl/HoldToConfirm.tsx`.
- **Tests:** A release before 800ms does not trigger the action; holding for the full duration does; the keyboard equivalent (a held keypress or explicit two-step dialog) produces the identical outcome.
- **Expected Output:** Both the mouse/touch gesture and its accessible equivalent independently trigger the same backend call.
- **Acceptance Criteria:** No safety-critical action in this UI is reachable via the gesture alone without an accessible equivalent — verified explicitly, per §10's accessibility requirement.
- **Dependencies:** M130.
- **Risk:** Medium.
- **Estimated Time:** 2h

### M132. Build the Knowledge Copilot Chat UI
- **Objective:** §11's chat column, source-citation strip, and Context Panel.
- **Files:** `apps/web/src/screens/KnowledgeCopilot/Chat.tsx`.
- **Tests:** A mock streaming response renders progressively with the documented retrieval-status sequence ("Searching incident history…", etc.) before the final answer.
- **Expected Output:** Status-line sequence and streaming both visible and correctly ordered.
- **Acceptance Criteria:** Citation chips render with distinct icons per source type (document/incident/graph-node), not color-only differentiation.
- **Dependencies:** M113.
- **Risk:** Low.
- **Estimated Time:** 3h

### M133. Wire Knowledge Copilot to the RAG System
- **Objective:** Connect M132 to M94's Knowledge Agent wrapper, with real token streaming.
- **Files:** `apps/web/src/screens/KnowledgeCopilot/useCopilotStream.ts`.
- **Tests:** A real query against the seeded corpus (M86) returns a grounded, cited answer rendered correctly in the UI.
- **Expected Output:** An end-to-end query through the actual UI produces the exact same verified answer M86's backend test already confirmed.
- **Acceptance Criteria:** The explicit-refusal case (an unanswerable query) renders in the visually-distinct "low confidence / no source" style specified in §11, not styled identically to a confident answer.
- **Dependencies:** M132, M86, M94.
- **Risk:** Medium.
- **Estimated Time:** 2h

### M134. Build the Reports Screen
- **Objective:** §12's report-type gallery and generated-report viewer.
- **Files:** `apps/web/src/screens/Reports/Reports.tsx`.
- **Tests:** Generating a report against seeded data produces a viewer showing the documented staged-progress sequence, then a populated report.
- **Expected Output:** A generated report's charts match the underlying seeded data.
- **Acceptance Criteria:** Partial-data annotation behavior (§12) verified by simulating one unavailable data source during generation.
- **Dependencies:** M36, M113.
- **Risk:** Low.
- **Estimated Time:** 3h

### M135. Build the Compliance Screen
- **Objective:** §13's dense audit-log table with lock-icon tamper-evidence indicators and the "Verify Integrity" action.
- **Files:** `apps/web/src/screens/Compliance/Compliance.tsx`.
- **Tests:** "Verify Integrity" against unmodified seeded audit data returns pass; against a (test-only, directly-manipulated-at-the-storage-layer) tampered record returns fail.
- **Expected Output:** Both verification outcomes render correctly and distinctly.
- **Acceptance Criteria:** Table is append-only in its rendering behavior — never re-orders or visually mutates existing rows on live update, only appends new ones, per §13's spec.
- **Dependencies:** M54, M107, M113.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M136. Build the Settings Screen
- **Objective:** §14's category navigation and the live-threshold-preview slider mechanic.
- **Files:** `apps/web/src/screens/Settings/Settings.tsx`.
- **Tests:** Dragging a threshold slider updates the live preview count against real seeded asset data before any save; an explicit "Save" step is required to persist.
- **Expected Output:** Preview updates instantly; no backend write occurs until Save is clicked.
- **Acceptance Criteria:** The explicit-save-step-for-safety-relevant-settings rule (§14) verified — no auto-save-on-drag behavior exists.
- **Dependencies:** M113, M48.
- **Risk:** Low.
- **Estimated Time:** 3h

### M137. Build the Admin Screen — Users & Roles
- **Objective:** §15's role×scope matrix picker, directly mirroring the `(Role, Resource Scope)` model from `user_role_scopes` (M21).
- **Files:** `apps/web/src/screens/Admin/UsersRoles.tsx`.
- **Tests:** Granting a zone-scoped role via the UI produces the exact correct `user_role_scopes` row.
- **Expected Output:** UI-driven grant matches what a direct API call to M48's RBAC system would produce.
- **Acceptance Criteria:** The matrix UI's shape matches the underlying data model's shape exactly, per §15's explicit design goal (reducing Admin misconfiguration risk).
- **Dependencies:** M21, M48, M113.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M138. Build the Admin Sensor Onboarding Wizard
- **Objective:** §15's guided, multi-step sensor-registration flow with live connectivity handshake feedback.
- **Files:** `apps/web/src/screens/Admin/SensorOnboarding.tsx`.
- **Tests:** Registering a new sensor through the wizard produces a correct `sensors` row and the sensor is queryable in Sensor Analytics (M128) immediately after.
- **Expected Output:** A wizard-onboarded sensor is fully live and visible system-wide with zero additional manual step, per the "new sensor requires zero new rules" goal established across this whole series.
- **Acceptance Criteria:** Failure cases (a deliberately-broken test protocol handshake) show the specific, technical diagnostic detail §15 calls for, not a generic error.
- **Dependencies:** M18, M113.
- **Risk:** Low.
- **Estimated Time:** 3h

---

## Phase 10 — Digital Twin 3D Engine (M139-M156)
Implements `DIGITAL_TWIN_EXPERIENCE.md`.

### M139. Set Up the WebGL Scene Renderer Skeleton
- **Objective:** A bare three.js (or equivalent) canvas with a camera, one light, and one test cube — proving the render loop before any real content.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/Scene.ts`.
- **Tests:** A smoke test asserting the canvas mounts and renders at least one frame without a WebGL context error.
- **Expected Output:** A rotating test cube renders in-browser.
- **Acceptance Criteria:** Frame rate logged and above 30fps on a baseline test machine with just the test cube.
- **Dependencies:** M111.
- **Risk:** Low.
- **Estimated Time:** 2h

### M140. Generate the Scene Graph From the Knowledge Graph
- **Objective:** §1.1 — a query-and-build step turning `KNOWLEDGE_GRAPH.md` §6's topology into a three.js scene-graph hierarchy automatically.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/scene-graph-builder.ts`.
- **Tests:** Build the scene from M69's seeded topology; verify object count and parent-child nesting exactly matches the graph query's output (10 zones, 40 equipment, correctly nested).
- **Expected Output:** The 3D scene's object hierarchy is programmatically verified to match the Neo4j query result, not just visually plausible.
- **Acceptance Criteria:** Adding a new equipment node to the graph (test-only) and re-running the builder produces the new object with zero manual scene-authoring step, per §1.1's onboarding guarantee.
- **Dependencies:** M139, M67.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M141. Implement the PBR Material System
- **Objective:** §1.3 — metalness/roughness materials for the base equipment-type set, stylized-but-precise per `ARCHITECTURE.md` §16.5.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/materials/pbr-material-library.ts`.
- **Tests:** A lighting-response visual test (a fixed light rotating around a test valve mesh) confirming the material responds physically (specular highlight moves correctly with light position).
- **Expected Output:** Visual proof the material isn't a flat, unlit color.
- **Acceptance Criteria:** At least 4 distinct material presets (steel, painted-metal, glass/gauge, concrete) covering the seeded equipment types.
- **Dependencies:** M139.
- **Risk:** Low.
- **Estimated Time:** 3h

### M142. Implement Procedural Pipeline Mesh Generation
- **Objective:** §2.2 — spline-based tube-mesh generation from `Pipeline` node `FLOWS_TO`/`INSTALLED_ON` topology (M69's seed data).
- **Files:** `apps/web/src/screens/DigitalTwin/engine/pipeline-generator.ts`.
- **Tests:** Generate pipeline geometry from the seeded topology; verify each segment's rendered diameter matches its `diameterMm` property and its path correctly connects its two graph-defined endpoints.
- **Expected Output:** Visual + programmatic check that generated pipe geometry connects the correct equipment pair.
- **Acceptance Criteria:** A branching (non-linear) topology segment (per M69's requirement) renders correctly as two distinct branches, not a single averaged path.
- **Dependencies:** M140, M69.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M143. Implement the Live Telemetry Data Binding Layer
- **Objective:** §1.4 — the uniform `{entity_id, property, value, timestamp}` interface that every subsequent animation system binds to, sourced from the live WebSocket for now (historical source added in M154).
- **Files:** `apps/web/src/screens/DigitalTwin/engine/data-binding-layer.ts`.
- **Tests:** A live sensor value change over the WebSocket updates a bound test property (e.g., a gauge rotation) within one render frame of arrival.
- **Expected Output:** Changing a value via the simulator visibly updates the 3D scene almost immediately.
- **Acceptance Criteria:** The binding interface is provably data-source-agnostic — verified by later swapping in M154's historical query source with zero changes to this layer's consumers.
- **Dependencies:** M140, M50, M63.
- **Risk:** Medium — this is the architectural linchpin for live/replay parity (§9.1).
- **Estimated Time:** 3h

### M144. Implement Worker Avatar + Path Interpolation
- **Objective:** §3.1 — generic low-poly figures, position-interpolated (never teleporting) between Worker Agent updates.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/entities/WorkerAvatar.ts`.
- **Tests:** Feed two position updates 5 seconds apart; verify the avatar's rendered position at the 2.5-second mark is interpolated, not snapped to either endpoint.
- **Expected Output:** Smooth, continuous motion confirmed programmatically (position sampled mid-transition).
- **Acceptance Criteria:** Avatar carries zero identifying visual detail, per §3.1's privacy requirement (a visual/code review checklist item, not just a test assertion).
- **Dependencies:** M143, M91.
- **Risk:** Low.
- **Estimated Time:** 3h

### M145. Implement Machine Animation State Binding
- **Objective:** §3.2 — rotor/animation state driven directly by `machine_state_history.operating_state`.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/entities/MachineAnimator.ts`.
- **Tests:** Feed `running`, `idle`, and `faulted` states in sequence; verify the corresponding rotor-spin, freeze, and juddering-plus-tint states each render correctly and only in response to real state changes.
- **Expected Output:** All three states visually and programmatically distinct.
- **Acceptance Criteria:** No animation plays when data is stale/missing — verified by disconnecting the data source and confirming the "last known state" treatment activates, not a default idle loop (§7.1).
- **Dependencies:** M143, M100.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M146. Implement Risk Zone Volumetric Wash Overlay
- **Objective:** §5.1 — translucent 3D zone-boundary rendering, severity-colored, with the one-time-pulse-then-steady motion rule.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/overlays/RiskZoneOverlay.ts`.
- **Tests:** A severity-tier change triggers exactly one pulse animation, then settles to a steady wash — verified by counting animation-loop iterations (must be finite, not continuous).
- **Expected Output:** No looping/flashing animation ever occurs, matching the alarm-fatigue rule from `UI_UX_SPECIFICATION.md` §0.2.
- **Acceptance Criteria:** Explicitly tested against a rapid back-to-back severity change to confirm no animation pile-up or stutter.
- **Dependencies:** M143, M104.
- **Risk:** Low.
- **Estimated Time:** 2h

### M147. Implement Camera/Sensor Marker Overlay with Clustering
- **Objective:** §5.3-5.4 — toggleable FOV cones and scale-aware sensor clustering.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/overlays/MarkerOverlay.ts`.
- **Tests:** With the seeded 100 sensors, verify markers cluster below a defined zoom threshold and de-cluster progressively above it.
- **Expected Output:** Marker count on screen changes correctly and smoothly across the zoom range, never showing 100 unreadable overlapping icons at wide zoom.
- **Acceptance Criteria:** Clustering behavior is the specific thing under test, not just marker existence.
- **Dependencies:** M140, M32.
- **Risk:** Low.
- **Estimated Time:** 2h

### M148. Implement Gas Cloud Volumetric Shader
- **Objective:** §4.1 — a density-field cloud driven by gas-sensor concentration and a lightweight Gaussian-plume dispersion approximation.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/hazards/GasCloudRenderer.ts`.
- **Tests:** Feed a known concentration + wind-direction test input; verify the rendered cloud's centroid drifts in the correct wind-informed direction, and its color/opacity mapping matches the same sigmoid curve used in `RISK_FUSION_ENGINE.md` §3.4 (shared constant, not a re-tuned duplicate).
- **Expected Output:** Cloud shape and color respond correctly to both inputs.
- **Acceptance Criteria:** The color-curve-sharing requirement is explicitly verified (import/reference the same threshold constant used by M98's Explosion network, not a separately hand-tuned value).
- **Dependencies:** M143, M96.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M149. Implement Fire Particle System
- **Objective:** §4.2 — particle-based flame/smoke, triggered only on confirmed detection or active Emergency Event, never speculatively.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/hazards/FireRenderer.ts`.
- **Tests:** A predicted-but-unconfirmed high-Fire-score test case must NOT render flame particles; a confirmed Vision Agent fire-detection event must.
- **Expected Output:** Both cases produce the correct, distinct rendering outcome.
- **Acceptance Criteria:** The predicted-vs-confirmed distinction is the specific, explicit thing under test — this is the milestone most directly enforcing §4.2's "never speculative" rule.
- **Dependencies:** M143, M90.
- **Risk:** Medium.
- **Estimated Time:** 2h

### M150. Implement the Risk Heat Map Shader (MVP: One Mode)
- **Objective:** §6.1 — the Risk heat-map mode (Thermal and Occupancy modes deferred as separate follow-on milestones once their underlying data — Vision Agent thermal frames, Worker Agent density — is solid).
- **Files:** `apps/web/src/screens/DigitalTwin/engine/overlays/HeatMapRenderer.ts`.
- **Tests:** A known spatial risk-score distribution across test zones produces a visually and programmatically correct density gradient.
- **Expected Output:** Heat-map density correctly reflects the underlying `risk_scores` spatial distribution.
- **Acceptance Criteria:** Toggle-only, single-mode-at-a-time behavior verified — the UI cannot enable two heat-map modes simultaneously, per §6.1's "never combined" rule.
- **Dependencies:** M146.
- **Risk:** Low.
- **Estimated Time:** 2h

### M151. Implement the Predictive Overlay (Ghost Rendering)
- **Objective:** §6.2 — dashed/translucent forward-projection of a hazard's forecast boundary, using the ghost material convention.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/overlays/PredictiveOverlay.ts`.
- **Tests:** A test prediction with a forecast dispersion boundary renders as a distinctly dashed, higher-transparency extension beyond the confirmed cloud from M148 — verified as visually and materially distinct, not just positioned further out.
- **Expected Output:** Ghost material is provably different (shader/material property diff) from the solid material used for confirmed hazards.
- **Acceptance Criteria:** This is the single most important visual-language rule in the whole 3D engine (per `DIGITAL_TWIN_EXPERIENCE.md` §6.2's own framing) — the material distinction is asserted in code, not left to visual inspection alone.
- **Dependencies:** M148, M104.
- **Risk:** High — getting this ambiguous would violate the core explainability commitment the whole series is built on.
- **Estimated Time:** 3h

### M152. Implement the Camera Rig (Orbit/Walkthrough/Top-Down)
- **Objective:** §8.1 — all three camera modes, including Walkthrough's collision detection against building/equipment geometry.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/camera/CameraRig.ts`.
- **Tests:** Walkthrough mode against a test wall must stop the camera at the wall surface, never clip through it; Orbit mode correctly snaps focus to a newly-selected entity.
- **Expected Output:** All three modes function correctly; the clip-through failure case is explicitly reproduced-then-fixed as part of this milestone's test.
- **Acceptance Criteria:** Collision detection verified against at least one building wall and one large equipment mesh.
- **Dependencies:** M140.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M153. Implement GPU Object-ID Picking
- **Objective:** §8.2 — hidden ID-buffer render pass for O(1) click-selection at scale.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/picking/GpuPicker.ts`.
- **Tests:** With all seeded objects in scene, click-selection correctness verified against at least 10 distinct objects; a performance test confirms picking latency doesn't scale with object count the way naive raycasting would (measured, not assumed).
- **Expected Output:** Picking remains fast and accurate at the full seeded object count.
- **Acceptance Criteria:** Selection highlight (Aegis Cyan for AI-content selections, neutral otherwise, per §8.3) correctly applied post-pick.
- **Dependencies:** M140.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M154. Implement the Playback Scrubber + Historical Query Binding
- **Objective:** §9.1-9.2 — swap the Data Binding Layer (M143) to a historical continuous-aggregate query source, plus the VCR-style scrub UI.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/playback/PlaybackController.ts`.
- **Tests:** Scrubbing to a known past timestamp reproduces the exact scene state (equipment states, worker positions) that existed at that time, verified against the stored historical data directly.
- **Expected Output:** Replayed scene state matches ground truth exactly for a chosen historical instant.
- **Acceptance Criteria:** **Zero code changes were required in any consumer of the Data Binding Layer** (M144-M151) to support this — the specific architectural claim from §1.4/§9.1 is verified as literally true, not just aspirationally true.
- **Dependencies:** M143, M40, M144, M145, M146.
- **Risk:** High — this is the load-bearing proof of the entire live/replay-parity architectural claim.
- **Estimated Time:** 3h

### M155. Implement Time-Travel Jump-to-Date Control
- **Objective:** §9.3 — direct timestamp navigation, plus RAG `as_of` parameter integration for time-travel-aware Knowledge Copilot queries.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/playback/TimeTravelPicker.ts`.
- **Tests:** Jumping to a past date, then issuing a Knowledge Copilot query, returns an answer grounded in the document version that was actually effective at that date (per `RAG_SYSTEM.md` §5.4) — verified using a test document with two versions with different effective dates.
- **Expected Output:** The correct historical document version is cited, not the currently-effective one.
- **Acceptance Criteria:** This cross-system integration (3D time-travel state → RAG `as_of` parameter) is the specific thing under test.
- **Dependencies:** M154, M133.
- **Risk:** Medium.
- **Estimated Time:** 2h

### M156. Implement the Digital Twin Mini-Viewport for the Dashboard
- **Objective:** §16's embedded live preview, click-to-expand into the full Digital Twin screen.
- **Files:** `apps/web/src/screens/Dashboard/widgets/TwinMiniViewport.tsx`.
- **Tests:** The mini-viewport renders the same live scene state as the full screen simultaneously (both subscribed to the same live data); clicking it navigates to the full view without losing camera context.
- **Expected Output:** Mini and full views never visually disagree about current state.
- **Acceptance Criteria:** Performance-budgeted separately from the full-screen view (lower LOD, per §1.3/§10) since it renders alongside five other Dashboard widgets simultaneously.
- **Dependencies:** M140, M120.
- **Risk:** Low.
- **Estimated Time:** 2h

---

## Phase 11 — Real-Time Integration (M157-M160)
Wires the Realtime Gateway (scaffolded in M50) to every live consumer built in Phases 9-10.

### M157. Wire Realtime Gateway to Dashboard Live Widgets
- **Objective:** Replace every Dashboard widget's remaining mock-data path with the real Realtime Gateway subscription.
- **Files:** `services/realtime-gateway/src/channels/risk-feed.channel.ts`, `apps/web/src/hooks/useRealtimeSubscription.ts`.
- **Tests:** A simulated risk-score change reaches the Dashboard UI within the `NFR-6` 1Hz-perceived-refresh target, measured end to end.
- **Expected Output:** Measured latency logged and within target.
- **Acceptance Criteria:** All 6 Dashboard widgets (M120-M122) confirmed live, none still on mock data.
- **Dependencies:** M50, M122.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M158. Wire Realtime Gateway to the Digital Twin Scene
- **Objective:** Connect the Data Binding Layer (M143) to the actual Realtime Gateway rather than a direct test WebSocket.
- **Files:** `apps/web/src/screens/DigitalTwin/engine/data-binding-layer.ts` (update), `services/realtime-gateway/src/channels/twin-state.channel.ts`.
- **Tests:** A live simulator-driven scenario (M60) is visibly reflected in the 3D scene end to end, from sensor to pixel.
- **Expected Output:** Running the M60 scenario live shows the corresponding gas cloud/machine-state changes appear in the 3D view in real time.
- **Acceptance Criteria:** This is the first true full-stack demo of the "Predicted Leak" journey rendered visually, not just asserted in a backend test (M110).
- **Dependencies:** M143, M50, M60.
- **Risk:** Medium.
- **Estimated Time:** 3h

### M159. Implement Zone-Scoped Subscription Filtering
- **Objective:** `ARCHITECTURE.md` §11.2's bandwidth-bounding requirement — clients subscribe only to zones currently in view.
- **Files:** `services/realtime-gateway/src/subscription-manager.ts`.
- **Tests:** A client viewing only Zone 3 must not receive telemetry updates for Zone 7; changing viewport must update the active subscription set.
- **Expected Output:** Message volume received by a test client scales with viewed zones, not total plant zones.
- **Acceptance Criteria:** Verified with a message-count assertion, not just a visual spot-check.
- **Dependencies:** M157, M158.
- **Risk:** Medium — this is the mechanism NFR-7's scale target depends on.
- **Estimated Time:** 2h

### M160. Implement the `pg_notify` → Realtime Gateway Bridge for Alerts
- **Objective:** Connect M28's Postgres `pg_notify` trigger to the Realtime Gateway, closing the low-latency alert-delivery path described in `DATABASE_SCHEMA.md` §11.
- **Files:** `services/realtime-gateway/src/listeners/pg-notify-bridge.ts`.
- **Tests:** Inserting a Critical alert directly into `alerts` reaches a subscribed UI client within the `NFR-5` 10-second target, measured end to end.
- **Expected Output:** Measured latency well under target (this path is designed to be near-instant).
- **Acceptance Criteria:** Verified as the fastest path in the system, faster than the Kafka-consumer-based paths used elsewhere, per its designed purpose.
- **Dependencies:** M28, M50.
- **Risk:** Low.
- **Estimated Time:** 2h

---

## Phase 12 — Emergency Response End-to-End (M161-M164)

### M161. Seed a Demo Playbook: Gas Leak Response
- **Objective:** A real, complete playbook (`playbooks`/`playbook_steps`) matching the Gas Leak hazard class, with a mix of autonomy tiers per step, per `ARCHITECTURE.md` §15.2's example.
- **Files:** `services/agentic-orchestrator/scripts/seed-gas-leak-playbook.sql`.
- **Tests:** Query the seeded playbook via M105's matcher against a Gas Leak-classified risk assessment; verify a correct match.
- **Expected Output:** The matcher returns this exact playbook for a Gas Leak scenario.
- **Acceptance Criteria:** At least one Tier 1 (approval-required) and one Tier 2 (execute-with-notification) step present, to exercise both gates in M164's end-to-end test.
- **Dependencies:** M30, M105.
- **Risk:** Low.
- **Estimated Time:** 2h

### M162. Wire Emergency Agent Execution to the Notification Service
- **Objective:** Connect M106's tool-calling `notify()` call to M53's real Notification Service dispatch.
- **Files:** `services/agentic-orchestrator/src/tools/notify.tool.ts`.
- **Tests:** A playbook step's `notify()` call produces a real `notifications` row that M53 dispatches and M116's UI tray displays.
- **Expected Output:** A playbook-triggered notification is visible in the actual UI, not just present in the database.
- **Acceptance Criteria:** Full path (tool call → DB row → dispatch → UI) verified in one test, not per-segment only.
- **Dependencies:** M106, M53, M116.
- **Risk:** Low.
- **Estimated Time:** 2h

### M163. Wire the Emergency Control Screen's Approve Action to Emergency Agent
- **Objective:** Connect M131's press-and-hold confirmation to a real API call that publishes the approval event M106's step sequencer is waiting on.
- **Files:** `apps/web/src/screens/EmergencyControl/api/approve-step.ts`, `services/agentic-orchestrator/src/api/approvals.controller.ts`.
- **Tests:** Approving a Tier 1 step in the real UI causes the real backend sequencer to proceed to execution — verified by observing the actual `emergency_event_steps.status` transition.
- **Expected Output:** A UI action causes a real, observable backend state change.
- **Acceptance Criteria:** This is the first milestone connecting a human action in the UI to the structural approval-gate proven at the backend level in M106.
- **Dependencies:** M131, M106.
- **Risk:** Medium.
- **Estimated Time:** 2h

### M164. End-to-End Test: Simulated Leak → Prediction → Incident → Playbook → Approval → Execution
- **Objective:** The single largest integration test in the roadmap — the full "Predicted Leak" journey (`ARCHITECTURE.md` §5.1), now including the frontend, Digital Twin, and a real human-approval step via the UI (not just the backend-only version already proven in M110).
- **Files:** `e2e/predicted-leak-full-stack.test.ts` (a browser-automation test, e.g. Playwright).
- **Tests:** Start M60's scenario; assert, via the actual rendered UI: the Risk Feed shows the escalating item, the Digital Twin shows the developing gas cloud, the Emergency Control screen receives the proposed playbook, a simulated human approves it via the real press-and-hold interaction, and the playbook executes with the notification visible in the tray.
- **Expected Output:** A recorded end-to-end run (screenshot/video capture) demonstrating the entire product narrative from `ARCHITECTURE.md` §5.1 functioning as one coherent system.
- **Acceptance Criteria:** This is the demo. If this test passes reliably, the hackathon demo is not a scripted illusion — it is this test, run live.
- **Dependencies:** M110, M158, M163.
- **Risk:** High — the single highest-value and highest-integration-risk milestone in the entire roadmap.
- **Estimated Time:** 3h

---

## Phase 13 — Compliance & Hardening (M165-M170)

### M165. Implement the Audit Log Integrity Verification Job
- **Objective:** `AGENT_ARCHITECTURE.md` §10's tamper-evidence hash-chain check, run against real seeded audit history.
- **Files:** `services/audit-log/src/jobs/integrity-verification.job.ts`.
- **Tests:** Verification passes against unmodified data; fails against a test record altered directly at the storage layer (bypassing the application, simulating a compromised-role scenario).
- **Expected Output:** Both cases produce the correct verdict.
- **Acceptance Criteria:** This is the automated version of M135's UI-level "Verify Integrity" action — same underlying check, now scheduled.
- **Dependencies:** M34, M107.
- **Risk:** Medium.
- **Estimated Time:** 2h

### M166. Implement Retention Policy Enforcement Job
- **Objective:** A scheduled check confirming every table's actual data age against its configured retention window (`DATABASE_SCHEMA.md` §22.3), flagging drift.
- **Files:** `services/audit-log/src/jobs/retention-check.job.ts`.
- **Tests:** Verify the job correctly identifies a deliberately-misconfigured retention policy in a test environment.
- **Expected Output:** Misconfiguration is caught and reported, not silently ignored.
- **Acceptance Criteria:** `audit_logs`' deliberate retention-policy exclusion (never dropped, per `NFR-17`) is confirmed correctly excluded from this check's "should have a retention policy" assertion.
- **Dependencies:** M42.
- **Risk:** Low.
- **Estimated Time:** 2h

### M167. Implement the Compliance Export PDF Generator
- **Objective:** `UI_UX_SPECIFICATION.md` §13's "Export for Regulatory Submission" — a formatted, indexed package, not a raw CSV dump.
- **Files:** `services/audit-log/src/export/regulatory-export.service.ts`.
- **Tests:** Generate an export for a seeded date range; verify every entry in the PDF is traceable back to a real `audit_logs` row (no summarization drift).
- **Expected Output:** A real, readable PDF matching the underlying data exactly.
- **Acceptance Criteria:** Export always renders in the light/print theme regardless of the live app's current theme, per the export-theming rule established in `UI_UX_SPECIFICATION.md` §5/§12.
- **Dependencies:** M135, M165.
- **Risk:** Low.
- **Estimated Time:** 3h

### M168. Security Review: RBAC Enforcement Test Suite
- **Objective:** A dedicated, adversarial test suite attempting to bypass RBAC at every layer (`ARCHITECTURE.md` §21.3's three enforcement layers), not just the happy path already covered in M48.
- **Files:** `services/identity-rbac/tests/security/rbac-bypass-attempts.test.ts`.
- **Tests:** Attempt cross-zone access with a manipulated JWT claim; attempt a direct API call bypassing the UI's role-based hiding; attempt an SQL-level query as a role without row-level access.
- **Expected Output:** Every bypass attempt is correctly rejected at the appropriate layer.
- **Acceptance Criteria:** At least one test per enforcement layer (Gateway, Service, Data/RLS) from `ARCHITECTURE.md` §21.3, each independently defeating a different bypass strategy.
- **Dependencies:** M48, M137.
- **Risk:** High — this is the last line of defense before a real security review; findings here are cheaper to fix now than after deployment.
- **Estimated Time:** 3h

### M169. Load Test: Sensor Ingestion at Target Throughput
- **Objective:** Validate the ingestion path (M63) and `sensor_readings`' 2D partitioning (M38) under a load approximating a meaningful fraction of the `NFR-7` commercial-scale target, not just the hackathon's ~100-sensor demo footprint.
- **Files:** `scripts/load-test/sensor-ingestion-load.ts`.
- **Tests:** Simulate a substantially higher sensor count/frequency than the demo dataset; measure ingestion latency and confirm it stays within the `NFR-4` (<2s anomaly-flag) budget under load.
- **Expected Output:** A load-test report showing latency percentiles at the tested scale.
- **Acceptance Criteria:** No data loss under load; latency degradation, if any, is measured and documented, not silently accepted.
- **Dependencies:** M63, M38, M87.
- **Risk:** Medium — this is the first real evidence for or against the commercial-scalability claims made throughout the design series.
- **Estimated Time:** 3h

### M170. Demo Scenario Scripting and Rehearsal Checklist
- **Objective:** A repeatable, documented demo script driving M164's end-to-end scenario for live presentation, plus a pre-demo environment-health checklist.
- **Files:** `docs/DEMO_SCRIPT.md`, `scripts/demo-environment-check.sh`.
- **Tests:** A full dry-run of the demo script against a freshly-reseeded environment (M43), timed.
- **Expected Output:** A complete, timed run-through with no manual intervention required beyond the scripted narrative beats.
- **Acceptance Criteria:** The environment-health checklist independently verifies every service from Phase 2 is healthy before the demo begins — no demo-day surprises from a silently-down dependency.
- **Dependencies:** M164, M43.
- **Risk:** Low — but the cost of skipping this is a live-demo failure, so it is not optional.
- **Estimated Time:** 2h

---

## Closing Summary

**170 milestones, 14 phases, every one grounded in a named artifact from the eight prior design documents** — no milestone in this roadmap describes generic work ("build the backend," "make the UI nice"); every one builds a specific table, agent, screen, or shader already specified elsewhere in this series, and every one has a test that would fail if the corresponding design document's stated behavior weren't actually implemented. Total estimated effort at the stated per-milestone times: approximately **440-460 hours** of focused engineering work, most of it parallelizable across engineers once each phase's cross-cutting dependencies (Phase 1's database, Phase 3's event schemas, Phase 8's design system) are in place — those three phases are the critical path everything else waits on, and should be staffed and prioritized accordingly. The three milestones flagged **High risk** for reasons beyond ordinary implementation difficulty (M98's Explosion noisy-AND gate, M106/M109's human-approval-gate structural guarantees, M151's ghost-vs-solid rendering distinction, M164's full-stack demo) are the ones worth a second engineer's review before being marked done, regardless of how confident the implementer feels — they are, respectively, the mathematical, safety, trust, and narrative core of the entire product.

**End of Document.**

