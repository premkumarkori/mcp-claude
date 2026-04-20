"""CSV export of query results.

Large results are written to `./exports/{export_id}.csv` at query time, and
`export_csv(export_id)` returns the path. We don't stream CSV contents through
the MCP tool output — that defeats the whole point of avoiding large inline
results.
"""

from __future__ import annotations

import csv
import secrets
from pathlib import Path
from typing import Any


def new_export_id() -> str:
    return secrets.token_hex(8)


def write_csv(export_dir: Path, export_id: str, columns: list[str], rows: list[dict[str, Any]]) -> Path:
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"{export_id}.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def resolve_export_path(export_dir: Path, export_id: str) -> Path:
    """Resolve an export_id to a file path, guarding against path traversal."""
    if not export_id or "/" in export_id or "\\" in export_id or ".." in export_id:
        raise ValueError("Invalid export_id.")
    path = (export_dir / f"{export_id}.csv").resolve()
    export_root = export_dir.resolve()
    if export_root not in path.parents and path.parent != export_root:
        raise ValueError("export_id escapes export directory.")
    if not path.exists():
        raise FileNotFoundError(f"No export for id={export_id!r}.")
    return path
