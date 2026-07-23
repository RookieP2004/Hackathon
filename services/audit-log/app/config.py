from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Base settings every service inherits and extends. Field names match the
    root .env.example exactly — this is the contract that keeps configuration
    consistent across all 14 services without duplicating variable names.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aegis_env: str = "local"
    log_level: str = "info"
    service_name: str = "audit-log"
    service_port: int = 8000

    database_url: str = "postgresql+asyncpg://aegis:changeme_local_only@localhost:5432/aegis"
    redis_url: str = "redis://localhost:6379/0"
    kafka_brokers: str = "localhost:9092"


@lru_cache
def get_settings() -> Settings:
    return Settings()
