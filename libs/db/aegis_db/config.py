from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://aegis:changeme_local_only@localhost:5432/aegis"

    @property
    def sync_database_url(self) -> str:
        """Alembic (and any sync-only tooling) needs a psycopg2 URL, not asyncpg."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


@lru_cache
def get_db_settings() -> DBSettings:
    return DBSettings()
