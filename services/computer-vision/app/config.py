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
    service_name: str = "computer-vision"
    service_port: int = 8000

    database_url: str = "postgresql+asyncpg://aegis:changeme_local_only@localhost:5432/aegis"
    redis_url: str = "redis://localhost:6379/0"
    kafka_brokers: str = "localhost:9092"

    jwt_secret: str = "changeme_generate_a_real_secret_before_any_shared_deployment"
    jwt_algorithm: str = "HS256"
    frontend_base_url: str = "http://localhost:3000"

    # Vision Agent's inputs/outputs -- ARCHITECTURE.md §18's "Integrate with
    # Risk Engine" requirement and this module's camera-feed source. No
    # existing service calls another service over HTTP yet (see
    # downstream.py's docstring for why this module still does), so these are
    # new settings specific to computer-vision, not inherited boilerplate.
    iot_simulator_ws_url: str = "ws://localhost:8014/ws/telemetry"
    notification_service_url: str = "http://localhost:8011"
    predictive_risk_engine_url: str = "http://localhost:8005"
    vision_service_actor_user_id: int = -1  # not a real users.id row -- create_alert/create_risk_score never look it up, only require_roles' role_id check


@lru_cache
def get_settings() -> Settings:
    return Settings()
