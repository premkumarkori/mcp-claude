"""FastMCP wiring for the Analytics MCP.

Uses individual typed params (FastMCP-idiomatic) for clean LLM-facing schemas.
"""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from . import tools as curated
from .audit import AuditLog
from .config import settings
from .db import DB
from .export import resolve_export_path
from .logging import configure as _configure_logging
from .logging import logger
from .pipeline import run_pipeline

_configure_logging(settings.log_level)

mcp = FastMCP("analytics")

_db = DB(settings.db_url)
_audit = AuditLog(settings.audit_log_path)
_connected = False


async def _ensure_db() -> None:
    global _connected
    if not _connected:
        await _db.connect()
        _connected = True


# --------------------------------------------------------------------------
# Schema / metadata tools
# --------------------------------------------------------------------------


@mcp.tool()
async def list_tables() -> dict[str, Any]:
    """List the views/tables the Analytics MCP is allowed to read."""
    logger.info("tool.list_tables")
    return await curated.list_tables(settings)


@mcp.tool()
async def describe_table(name: str) -> dict[str, Any]:
    """Return columns + types for an allowlisted view."""
    await _ensure_db()
    return (await curated.describe_table(name, db=_db, settings=settings, audit=_audit)).model_dump()


@mcp.tool()
async def get_row_count(table: str) -> dict[str, Any]:
    """Count rows in an allowlisted view."""
    await _ensure_db()
    return (await curated.get_row_count(table, db=_db, settings=settings, audit=_audit)).model_dump()


# --------------------------------------------------------------------------
# Curated query tools
# --------------------------------------------------------------------------


@mcp.tool()
async def recent_employees(days: int = 7) -> dict[str, Any]:
    """Employees who joined within the last `days` days (1..365)."""
    await _ensure_db()
    return (
        await curated.recent_employees(days, db=_db, settings=settings, audit=_audit)
    ).model_dump()


@mcp.tool()
async def orders_by_status(
    status: Literal["PENDING", "SHIPPED", "CANCELLED"],
) -> dict[str, Any]:
    """Orders filtered by status."""
    await _ensure_db()
    return (
        await curated.orders_by_status(status, db=_db, settings=settings, audit=_audit)
    ).model_dump()


@mcp.tool()
async def inactive_users(days: int = 30) -> dict[str, Any]:
    """Customer names with no orders in the last `days` days (1..365)."""
    await _ensure_db()
    return (
        await curated.inactive_users(days, db=_db, settings=settings, audit=_audit)
    ).model_dump()


# --------------------------------------------------------------------------
# Free-form SQL — 4-layer pipeline
# --------------------------------------------------------------------------


@mcp.tool()
async def run_query(sql: str) -> dict[str, Any]:
    """Execute a SELECT against allowlisted views, with all guardrails enforced.

    Rejects anything that isn't a single SELECT or references a non-allowlisted
    table/view. LIMIT is injected/capped. EXPLAIN cost is checked. Large results
    return a summary + export_id instead of inline rows.
    """
    await _ensure_db()
    return (
        await run_pipeline(sql, db=_db, settings=settings, audit=_audit, tool_name="run_query")
    ).model_dump()


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------


@mcp.tool()
async def export_csv(export_id: str) -> dict[str, Any]:
    """Return the filesystem path of a CSV created during a prior large-result query."""
    logger.info("tool.export_csv", export_id=export_id)
    try:
        path = resolve_export_path(settings.export_dir, export_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    return {"path": str(path), "size_bytes": path.stat().st_size}


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main() -> None:
    logger.info(
        "startup",
        allowlist=settings.table_allowlist,
        row_cap=settings.row_cap,
        inline_threshold=settings.inline_row_threshold,
    )
    mcp.run()


if __name__ == "__main__":
    main()
