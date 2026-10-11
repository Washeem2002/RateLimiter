from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "url-shortener"
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://shortener:shortener@localhost:5432/shortener"
    redis_url: str = "redis://localhost:6379/0"

    id_counter_offset: int = 1_000_000_000
    cache_ttl_seconds: int = 86400
    negative_cache_ttl_seconds: int = 60
    idempotency_ttl_seconds: int = 86400

    rate_limit_create_per_min: int = 10
    rate_limit_redirect_per_min: int = 300

    ip_hash_salt: str = "change-me-to-a-long-random-string"
    base_url: str = "http://localhost:8000"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    worker_batch_size: int = 500
    worker_poll_interval_seconds: float = 2.0
    worker_consumer_name: str = "click-worker"
    click_stream_key: str = "clicks"
    click_stream_group: str = "clicks-group"

    cache_lock_seconds: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
