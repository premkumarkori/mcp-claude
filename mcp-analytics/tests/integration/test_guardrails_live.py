"""End-to-end guardrail assertions against a real Postgres.

Requires Docker + `testcontainers`. Install with:
    pip install -e '.[integration]'

Run with:
    pytest -m integration

These tests prove the things unit tests CANNOT prove:
- The `mcp_readonly` DB role actually blocks writes at the DB layer.
- Non-allowlisted table access is refused end-to-end.
- Large-result queries produce a CSV + summary, not inline rows.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# Skip the whole module if testcontainers isn't installed.
testcontainers = pytest.importorskip("testcontainers.postgres")
asyncpg = pytest.importorskip("asyncpg")

from testcontainers.postgres import PostgresContainer  # noqa: E402

from mcp_analytics.audit import AuditLog  # noqa: E402
from mcp_analytics.config import Settings  # noqa: E402
from mcp_analytics.db import DB  # noqa: E402
from mcp_analytics.pipeline import run_pipeline  # noqa: E402
from mcp_analytics.validator import SqlValidationError  # noqa: E402


_SETUP_SQL = """
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW v_employees_safe AS
SELECT id, name,
       SUBSTRING(email FROM 1 FOR 2) || '***' AS email_masked,
       joined_at
FROM employees;

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW v_orders_safe AS
SELECT id, customer_name, amount, status, created_at FROM orders;

-- Seed enough rows to trigger the large-result path.
INSERT INTO employees (name, email, joined_at)
SELECT 'E' || i, 'e' || i || '@x.com', NOW() - (i || ' days')::interval
FROM generate_series(1, 120) i;

CREATE ROLE mcp_readonly LOGIN PASSWORD 'testpw'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
GRANT CONNECT ON DATABASE test TO mcp_readonly;
GRANT USAGE ON SCHEMA public TO mcp_readonly;
GRANT SELECT ON v_employees_safe TO mcp_readonly;
GRANT SELECT ON v_orders_safe TO mcp_readonly;
ALTER ROLE mcp_readonly SET default_transaction_read_only = on;
"""


@pytest.fixture(scope="module")
def pg():
    with PostgresContainer("postgres:16", dbname="test", username="app", password="app") as c:
        # Apply setup as superuser.
        import psycopg2  # testcontainers brings this in

        conn = psycopg2.connect(c.get_connection_url().replace("+psycopg2", ""))
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(_SETUP_SQL)
        conn.close()
        yield c


@pytest.fixture
def settings(pg, tmp_path) -> Settings:
    host = pg.get_container_host_ip()
    port = pg.get_exposed_port(5432)
    return Settings(
        db_url=f"postgresql://mcp_readonly:testpw@{host}:{port}/test",
        table_allowlist=["v_employees_safe", "v_orders_safe"],
        row_cap=1000,
        inline_row_threshold=50,
        max_plan_cost=10_000_000.0,
        audit_log_path=tmp_path / "audit.jsonl",
        export_dir=tmp_path / "exports",
        _env_file=None,
    )


async def _with_db(settings: Settings):
    db = DB(settings.db_url)
    await db.connect()
    return db


@pytest.mark.asyncio
async def test_readonly_role_blocks_insert(settings):
    """Layer 1 proof: the DB itself rejects writes for mcp_readonly."""
    conn = await asyncpg.connect(settings.db_url)
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "INSERT INTO employees(name,email) VALUES ('x','x@x.com')"
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_raw_table_access_refused(settings):
    """Layer 3 proof: parser rejects non-allowlisted references."""
    db = await _with_db(settings)
    audit = AuditLog(settings.audit_log_path)
    try:
        with pytest.raises(SqlValidationError, match="not in the allowlist"):
            await run_pipeline(
                "SELECT * FROM employees",
                db=db,
                settings=settings,
                audit=audit,
                tool_name="run_query",
            )
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_dml_refused_at_parser(settings):
    db = await _with_db(settings)
    audit = AuditLog(settings.audit_log_path)
    try:
        with pytest.raises(SqlValidationError):
            await run_pipeline(
                "DROP TABLE employees",
                db=db,
                settings=settings,
                audit=audit,
                tool_name="run_query",
            )
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_large_result_returns_summary_and_export(settings):
    """Layer 4 proof: >inline_threshold rows -> summary + export_id, no inline rows."""
    db = await _with_db(settings)
    audit = AuditLog(settings.audit_log_path)
    try:
        result = await run_pipeline(
            "SELECT * FROM v_employees_safe",
            db=db,
            settings=settings,
            audit=audit,
            tool_name="run_query",
        )
        assert result.row_count > settings.inline_row_threshold
        assert result.rows == []
        assert result.summary is not None
        assert result.export_id is not None
        csv_path = settings.export_dir / f"{result.export_id}.csv"
        assert csv_path.exists()
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_audit_log_has_entry_per_call_no_rows_leaked(settings):
    db = await _with_db(settings)
    audit = AuditLog(settings.audit_log_path)
    try:
        await run_pipeline(
            "SELECT id FROM v_employees_safe LIMIT 5",
            db=db,
            settings=settings,
            audit=audit,
            tool_name="run_query",
        )
        content = settings.audit_log_path.read_text()
        assert "SELECT id" in content
        # No row contents should appear in the audit log.
        assert '"rows"' not in content
        assert "@x.com" not in content
    finally:
        await db.close()
