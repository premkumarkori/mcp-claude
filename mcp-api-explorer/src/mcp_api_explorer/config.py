"""Environment-driven configuration.

All values come from env vars / `.env`. No hardcoded URLs, no hardcoded credentials.
Defaults are *safe*: `call_endpoint` is off, allowlist is localhost only.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Target API -----------------------------------------------------------
    api_base_url: str = "http://localhost:8080"
    openapi_path: str = "/v3/api-docs"
    spec_cache_ttl_seconds: int = 60

    # --- call_endpoint gating (safe defaults) --------------------------------
    allow_call: bool = False
    allow_mutating_calls: bool = False
    call_base_url_allowlist: list[str] = Field(
        default_factory=lambda: ["http://localhost:8080"]
    )
    call_timeout_seconds: float = 10.0

    # --- Logging -------------------------------------------------------------
    log_level: str = "INFO"

    @field_validator("call_base_url_allowlist", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        # Allow comma-separated env vars: CALL_BASE_URL_ALLOWLIST=a,b,c
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


settings = Settings()
