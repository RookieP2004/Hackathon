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
    service_name: str = "identity-rbac"
    service_port: int = 8000

    database_url: str = "postgresql+asyncpg://aegis:changeme_local_only@localhost:5432/aegis"
    redis_url: str = "redis://localhost:6379/0"
    kafka_brokers: str = "localhost:9092"

    # ARCHITECTURE.md §20 — JWT + refresh token configuration.
    jwt_secret: str = "changeme_generate_a_real_secret_before_any_shared_deployment"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    # Refresh tokens are opaque random strings (hashed at rest, aegis_db.models.auth.RefreshToken),
    # not JWTs themselves — only the short-lived access token is a JWT. This is what
    # makes access-token revocation-by-expiry cheap and refresh-token revocation
    # (rotation-on-use, theft detection) an explicit, auditable database operation.
    refresh_token_expire_days: int = 30
    password_reset_token_expire_minutes: int = 30

    frontend_base_url: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
