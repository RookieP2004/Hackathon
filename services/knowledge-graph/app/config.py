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
    service_name: str = "knowledge-graph"
    service_port: int = 8000

    database_url: str = "postgresql+asyncpg://aegis:changeme_local_only@localhost:5432/aegis"
    redis_url: str = "redis://localhost:6379/0"
    kafka_brokers: str = "localhost:9092"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme_local_only"
    frontend_base_url: str = "http://localhost:3000"

    # Shared JWT signing secret -- every service verifies tokens independently
    # (aegis_api_common.auth), never by calling identity-rbac per-request.
    jwt_secret: str = "changeme_generate_a_real_secret_before_any_shared_deployment"
    jwt_algorithm: str = "HS256"


@lru_cache
def get_settings() -> Settings:
    return Settings()
