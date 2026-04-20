"""Curated tools.

Every tool here goes through `run_pipeline`, so the guardrails apply uniformly
to free-form AND curated paths. The only thing curated tools skip is user-chosen
SQL — the SQL template is fixed in code and table names come from the allowlist.
"""

from __future__ import annotations

from typing import Literal

from .audit import AuditLog
from .config import Settings
from .db import DB
from .pagination import QueryResult
from .pipeline import run_pipeline

OrderStatus = Literal["PENDING", "SHIPPED", "CANCELLED"]


async def list_tables(settings: Settings) -> dict:
    """Returns the allowlisted table/view names."""
    return {"tables": list(settings.table_allowlist)}


async def describe_table(
    name: str, *, db: DB, settings: Settings, audit: AuditLog
) -> QueryResult:
    """Column names + types for a single allowlisted view.

    Queries `information_schema.columns` — this is NOT in the user-facing allowlist
    (and can't be, it's a system catalog), so we bypass run_pipeline for this
    read-only introspection and run a tightly parameterized query directly.
    """
    import time

    from .logging import logger

    if name.lower() not in settings.allowlist_set:
        raise ValueError(f"Table {name!r} is not in the allowlist.")

    t0 = time.monotonic()
    try:
        rows = await db.fetch(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position
            """,
            name,
        )
    except Exception as e:
        audit.record(
            tool="describe_table",
            params={"name": name},
            error=f"{type(e).__name__}: {e}",
            duration_ms=(time.monotonic() - t0) * 1000.0,
        )
        raise
    audit.record(
        tool="describe_table",
        params={"name": name},
        row_count=len(rows),
        duration_ms=(time.monotonic() - t0) * 1000.0,
    )
    logger.info("tool.describe_table", name=name, columns=len(rows))

    from .pagination import row_to_dict

    dict_rows = [row_to_dict(r) for r in rows]
    columns = list(dict_rows[0].keys()) if dict_rows else ["column_name", "data_type", "is_nullable"]
    return QueryResult(
        columns=columns,
        rows=dict_rows,
        row_count=len(dict_rows),
        truncated=False,
        summary=None,
        export_id=None,
    )


async def get_row_count(
    table: str, *, db: DB, settings: Settings, audit: AuditLog
) -> QueryResult:
    """Count rows in an allowlisted view. Safe because the table name is allowlist-checked."""
    if table.lower() not in settings.allowlist_set:
        raise ValueError(f"Table {table!r} is not in the allowlist.")
    sql = f"SELECT COUNT(*) AS count FROM {table}"  # noqa: S608 — table checked above
    return await run_pipeline(sql, db=db, settings=settings, audit=audit, tool_name="get_row_count")


async def recent_employees(
    days: int = 7, *, db: DB, settings: Settings, audit: AuditLog
) -> QueryResult:
    """Employees who joined within the last `days` days."""
    days = max(1, min(days, 365))
    sql = (
        "SELECT id, name, email_masked, joined_at "
        "FROM v_employees_safe "
        "WHERE joined_at >= NOW() - ($1::int * INTERVAL '1 day') "
        "ORDER BY joined_at DESC"
    )
    return await run_pipeline(
        sql,
        db=db,
        settings=settings,
        audit=audit,
        tool_name="recent_employees",
        params=(days,),
    )


async def orders_by_status(
    status: OrderStatus, *, db: DB, settings: Settings, audit: AuditLog
) -> QueryResult:
    """Orders filtered by status (PENDING / SHIPPED / CANCELLED)."""
    if status not in ("PENDING", "SHIPPED", "CANCELLED"):
        raise ValueError(f"Invalid status: {status!r}")
    sql = (
        "SELECT id, customer_name, amount, status, created_at "
        "FROM v_orders_safe "
        "WHERE status = $1 "
        "ORDER BY created_at DESC"
    )
    return await run_pipeline(
        sql,
        db=db,
        settings=settings,
        audit=audit,
        tool_name="orders_by_status",
        params=(status,),
    )


async def inactive_users(
    days: int = 30, *, db: DB, settings: Settings, audit: AuditLog
) -> QueryResult:
    """Customer names with no orders in the last `days` days.

    'Customer' here is the denormalized `customer_name` on orders — we don't
    have a real users table in v1.
    """
    days = max(1, min(days, 365))
    sql = (
        "SELECT DISTINCT customer_name "
        "FROM v_orders_safe "
        "WHERE customer_name NOT IN ("
        "  SELECT customer_name FROM v_orders_safe "
        "  WHERE created_at >= NOW() - ($1::int * INTERVAL '1 day')"
        ") "
        "ORDER BY customer_name"
    )
    return await run_pipeline(
        sql,
        db=db,
        settings=settings,
        audit=audit,
        tool_name="inactive_users",
        params=(days,),
    )
