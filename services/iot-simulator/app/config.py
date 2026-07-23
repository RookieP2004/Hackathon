from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Base settings every service inherits and extends. Field names match the
    root .env.example exactly — this is the contract that keeps configuration
    consistent across all services without duplicating variable names.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aegis_env: str = "local"
    log_level: str = "info"
    service_name: str = "iot-simulator"
    service_port: int = 8014

    frontend_base_url: str = "http://localhost:3000"

    # Added solely to back role-lookup queries for app/auth.py -- this
    # service otherwise owns no relational data of its own (its world is a
    # separate, fully in-memory synthetic simulation, per this service's own
    # docstrings).
    database_url: str = "postgresql+asyncpg://aegis:changeme_local_only@localhost:5432/aegis"
    jwt_secret: str = "changeme_generate_a_real_secret_before_any_shared_deployment"
    jwt_algorithm: str = "HS256"

    # Simulator-specific
    tick_interval_seconds: float = 1.0
    simulation_seed: int | None = None  # None = nondeterministic (real demo); set for reproducible tests


@lru_cache
def get_settings() -> Settings:
    return Settings()
