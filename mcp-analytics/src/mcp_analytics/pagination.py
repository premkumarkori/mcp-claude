"""Uniform result shape + summary builder for large results.

Rule: if row_count <= inline_threshold, return `rows` inline. Otherwise return
a `summary` + `export_id` and leave `rows` empty. Always return `columns` so
the LLM knows the shape.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    summary: dict[str, Any] | None = None
    next_cursor: str | None = None
    export_id: str | None = None


def _jsonable(v: Any) -> Any:
    """Coerce DB types into JSON-friendly values for tool output."""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def row_to_dict(row: Any) -> dict[str, Any]:
    """asyncpg Record -> plain dict with JSON-friendly values."""
    if hasattr(row, "keys"):
        return {k: _jsonable(row[k]) for k in row.keys()}
    return {k: _jsonable(v) for k, v in dict(row).items()}


def summarize(
    columns: list[str], rows: list[dict[str, Any]], top_k: int = 5
) -> dict[str, Any]:
    """Per-column summary: counts, nulls, min/max for ordered types, top-K for strings."""
    summary: dict[str, Any] = {"row_count": len(rows), "columns": {}}
    for col in columns:
        values = [r.get(col) for r in rows]
        non_null = [v for v in values if v is not None]
        col_summary: dict[str, Any] = {
            "non_null": len(non_null),
            "null": len(values) - len(non_null),
            "distinct": len({repr(v) for v in non_null}),
        }
        # Numeric / datetime: min + max.
        numeric_like = [v for v in non_null if isinstance(v, (int, float))]
        if numeric_like and len(numeric_like) == len(non_null):
            col_summary["min"] = min(numeric_like)
            col_summary["max"] = max(numeric_like)
        else:
            # Attempt ISO-date min/max as strings — cheap and useful.
            string_like = [v for v in non_null if isinstance(v, str)]
            if string_like and len(string_like) == len(non_null):
                counter = Counter(string_like)
                col_summary["top"] = counter.most_common(top_k)
        summary["columns"][col] = col_summary
    return summary


def build_result(
    columns: list[str],
    rows: list[dict[str, Any]],
    *,
    truncated: bool,
    inline_threshold: int,
    export_id: str | None,
) -> QueryResult:
    if len(rows) <= inline_threshold:
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            summary=None,
            export_id=None,
        )
    return QueryResult(
        columns=columns,
        rows=[],
        row_count=len(rows),
        truncated=truncated,
        summary=summarize(columns, rows),
        export_id=export_id,
    )
