"""The 4-layer execution pipeline used by every data-returning tool.

Order:
    1. validator.validate_select        (Layer 3)
    2. guardrails.ensure_limit          (Layer 4a — injected row cap)
    3. db.fetch_explain + cost check    (Layer 4b)
    4. db.fetch                         (Layer 1 + 2 enforced by DB role + session)
    5. pagination.build_result          (summarize / export-if-large)
    6. audit.record                     (append-only log)
"""

from __future__ import annotations

import time
from typing import Any

from .audit import AuditLog
from .config import Settings
from .db import DB
from .export import new_export_id, write_csv
from .guardrails import (
    assert_plan_within_budget,
    ensure_limit,
    extract_plan_total_cost,
)
from .logging import logger
from .pagination import QueryResult, build_result, row_to_dict
from .validator import validate_select


async def run_pipeline(
    sql: str,
    *,
    db: DB,
    settings: Settings,
    audit: AuditLog,
    tool_name: str,
    params: tuple[Any, ...] = (),
) -> QueryResult:
    """Run user-supplied or curated SQL through all four guardrail layers."""
    t0 = time.monotonic()
    err: str | None = None
    rendered_sql: str = sql
    result_row_count: int | None = None
    truncated: bool = False

    try:
        # Layer 3 — parser-level validation.
        tree = validate_select(sql, settings.allowlist_set)

        # Layer 4a — inject / cap LIMIT. We use row_cap + 1 internally so we can
        # detect whether the user asked for more than we're willing to return.
        capped_tree = ensure_limit(tree, settings.row_cap + 1)
        rendered_sql = capped_tree.sql(dialect="postgres")

        # Layer 4b — plan cost check.
        explain_rows = await db.fetch_explain(rendered_sql, *params)
        cost = extract_plan_total_cost(explain_rows)
        assert_plan_within_budget(cost, settings.max_plan_cost)

        # Execute.
        records = await db.fetch(rendered_sql, *params)

        # Build columns + trim to row_cap.
        if records:
            columns = list(records[0].keys())
        else:
            columns = []
        raw_rows = [row_to_dict(r) for r in records]
        truncated = len(raw_rows) > settings.row_cap
        rows = raw_rows[: settings.row_cap]
        result_row_count = len(rows)

        # Large-result path — write CSV + summarize.
        export_id: str | None = None
        if result_row_count > settings.inline_row_threshold:
            export_id = new_export_id()
            write_csv(settings.export_dir, export_id, columns, rows)

        return build_result(
            columns=columns,
            rows=rows,
            truncated=truncated,
            inline_threshold=settings.inline_row_threshold,
            export_id=export_id,
        )

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        logger.warning("pipeline.error", tool=tool_name, error=err)
        raise
    finally:
        audit.record(
            tool=tool_name,
            sql=rendered_sql,
            params={"args": list(params)} if params else None,
            row_count=result_row_count,
            truncated=truncated if result_row_count is not None else None,
            duration_ms=(time.monotonic() - t0) * 1000.0,
            error=err,
        )
