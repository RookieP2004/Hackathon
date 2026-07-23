#!/usr/bin/env bash
# Reseeds the local demo dataset (DEVELOPMENT_ROADMAP.md M43): 1 plant, 3 buildings,
# 10 zones, 40 equipment, 100 sensors, 5 workers/users, 2 permits — the fixed dataset
# every other milestone's manual testing and the M164 end-to-end demo depend on.
#
# Implemented in libs/db/seed/ (seed_lookups.py, seed_demo_plant.py, run_seed.py) —
# every step is independently idempotent, safe to re-run against an already-seeded
# database.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/libs/db"

poetry run python -m seed.run_seed
