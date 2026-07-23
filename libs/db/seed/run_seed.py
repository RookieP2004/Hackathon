"""
Entry point: `poetry run python -m seed.run_seed` (or via scripts/reseed-demo.sh).
Runs every seed step in dependency order. Each step is independently idempotent.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis_db.config import get_db_settings
from seed.seed_demo_plant import seed_demo_plant
from seed.seed_lookups import seed_lookups


def main() -> None:
    settings = get_db_settings()
    engine = create_engine(settings.sync_database_url)
    with Session(engine) as session:
        seed_lookups(session)
        seed_demo_plant(session)
    print("Seed complete.")


if __name__ == "__main__":
    main()
