"""Append-only JSONL audit log.

One line per tool invocation. Never contains raw result rows or secrets.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        tool: str,
        sql: str | None = None,
        params: dict[str, Any] | None = None,
        row_count: int | None = None,
        truncated: bool | None = None,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        entry = {
            "ts": datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds"),
            "tool": tool,
            "sql": sql,
            "params": params,
            "row_count": row_count,
            "truncated": truncated,
            "duration_ms": duration_ms,
            "error": error,
        }
        # Drop None fields for a cleaner log.
        entry = {k: v for k, v in entry.items() if v is not None}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
