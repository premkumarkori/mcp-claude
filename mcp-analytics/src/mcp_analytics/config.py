"""Environment-driven configuration.

Every value comes from env / `.env`. DSN is NEVER accepted from tool args.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_url: str = "postgresql://mcp_readonly:mcp_readonly_change_me@localhost:5432/appdb"

    table_allowlist: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["v_employees_safe", "v_orders_safe"]
    )

    row_cap: int = 1000
    inline_row_threshold: int = 50
    max_plan_cost: float = 100_000.0

    audit_log_path: Path = Path("./audit/queries.jsonl")
    export_dir: Path = Path("./exports")

    log_level: str = "INFO"

    @field_validator("table_allowlist", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [item.strip().lower() for item in v.split(",") if item.strip()]
        if isinstance(v, list):
            return [str(item).lower() for item in v]
        return v

    @property
    def allowlist_set(self) -> set[str]:
        return {t.lower() for t in self.table_allowlist}


settings = Settings()
