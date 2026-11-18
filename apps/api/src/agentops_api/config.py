
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    app_name: str = "AgentOps Control Tower API"

    app_env: str = "local"

    database_url: str

    # Dashboard local-auth session lifetime (M7). Not a secret - sessions are
    # opaque random tokens, hashed like API keys (see auth_service.py).
    session_ttl_minutes: int = 720  # 12 hours

    # Local-auth login throttling (M7): failed attempts allowed per email
    # within login_rate_limit_window_seconds before further attempts are
    # rejected without even checking the password.
    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:

    return Settings()
