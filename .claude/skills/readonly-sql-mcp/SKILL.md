---
name: readonly-sql-mcp
description: Use when implementing or extending the Analytics MCP (read-only NL-to-SQL against PostgreSQL). Triggers on "build the Analytics MCP", "add a data tool", "write a curated query tool", or work inside mcp-analytics/.
---

# readonly-sql-mcp

**Trigger:** work on the **Analytics MCP** (`mcp-analytics/`) — the server from [PRD.md](../../../PRD.md) §6.3. Build on top of [python-mcp-server](../python-mcp-server/SKILL.md).

**This is the highest-risk surface in the project.** The PRD §7 guardrails are non-negotiable. A single violation fails the milestone.

## Defense in depth (four layers — all must be present)

1. **Database layer** — dedicated read-only Postgres role, `GRANT SELECT` only on allowlisted views.
2. **Connection layer** — connection string uses `mcp_readonly`; `default_transaction_read_only=on` in the session.
3. **Parser layer** — `sqlglot` rejects non-`SELECT` or non-allowlisted references before execution.
4. **Execution layer** — `EXPLAIN` plan check, `LIMIT` enforced, timeout, row cap on fetch.

If any layer is missing, the skill has not been followed.

## Layer 1: Postgres role setup

In a Flyway migration in `springboot-api/`:

```sql
CREATE ROLE mcp_readonly LOGIN PASSWORD :'mcp_pw'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;

GRANT CONNECT ON DATABASE appdb TO mcp_readonly;
GRANT USAGE ON SCHEMA public TO mcp_readonly;

-- Only safe views — never raw tables with PII.
GRANT SELECT ON v_employees_safe TO mcp_readonly;
GRANT SELECT ON v_orders_safe TO mcp_readonly;

-- Belt and suspenders: set role default to read-only transactions.
ALTER ROLE mcp_readonly SET default_transaction_read_only = on;
ALTER ROLE mcp_readonly SET statement_timeout = '5s';
ALTER ROLE mcp_readonly SET idle_in_transaction_session_timeout = '10s';
```

Verify with `psql -U mcp_readonly -c "INSERT INTO ..."` — must fail. If it succeeds, stop.

## Layer 2: Connection

- `asyncpg` with the `mcp_readonly` DSN.
- Connection pool, size 5.
- On each acquire: `SET default_transaction_read_only = on; SET statement_timeout = '5s';` (redundant with role settings — belt and suspenders).
- Do **not** accept a DSN from tool args. Ever. DSN comes from env only.

## Layer 3: Parser-level validation (`sqlglot`)

Before any SQL touches the DB:

```python
import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"v_employees_safe", "v_orders_safe"}

def validate_select(sql: str) -> sqlglot.Expression:
    tree = sqlglot.parse_one(sql, dialect="postgres")

    # Must be a single SELECT (no CTEs-with-DML, no UNION to DML, etc.)
    if not isinstance(tree, exp.Select) and not (
        isinstance(tree, exp.Subqueryable) and tree.find(exp.Select)
    ):
        raise ValueError("Only SELECT queries are allowed.")
    for node in tree.walk():
        if isinstance(node[0], (exp.Insert, exp.Update, exp.Delete, exp.Merge,
                                 exp.Command, exp.Drop, exp.AlterTable, exp.Create)):
            raise ValueError("DML/DDL is not allowed.")

    # Allowlist check — every referenced table/view must be in the set.
    for table in tree.find_all(exp.Table):
        if table.name.lower() not in ALLOWED_TABLES:
            raise ValueError(f"Table {table.name!r} is not in the allowlist.")

    return tree
```

Reject with a clear message the LLM can use to retry with a valid query.

## Layer 4: Execution guardrails

### Force `LIMIT`
If the parsed tree has no `LIMIT`, inject `LIMIT <= ROW_CAP` (default 1000). If it has a `LIMIT` greater than `ROW_CAP`, lower it.

### `EXPLAIN` check
```python
plan = await conn.fetch(f"EXPLAIN (FORMAT JSON) {sql}")
# Reject if Total Cost > MAX_PLAN_COST, or any cartesian product node.
```

### Timeout
Rely on `statement_timeout = 5s` set on the role; also wrap the call in `asyncio.wait_for(..., timeout=6)` as a backstop.

### Row cap on fetch
Stop iterating the cursor at `ROW_CAP + 1` rows; if you hit `+1`, set `truncated: true`.

## Tool surface

### Free-form (gated)
- `run_query(sql: str)` — runs the 4-layer pipeline. Returns the pagination shape below.

### Curated (preferred)
- `list_tables()` → allowlist contents only.
- `describe_table(name)` → columns, types, sample row count.
- `get_row_count(table, filters?)` → forwards to a parameterized query, no free-form SQL.
- `recent_employees(days: int = 7)`
- `orders_by_status(status: Literal["pending","shipped","cancelled"])`
- `inactive_users(days: int = 30)`

**Rule of thumb:** if a question comes up more than twice, promote it from `run_query` to a curated tool.

## Pagination & large-result shape

Every data-returning tool returns this shape:

```python
class QueryResult(BaseModel):
    columns: list[str]
    rows: list[dict]            # empty if row_count > INLINE_ROW_THRESHOLD
    row_count: int              # actual count returned (pre-truncation)
    truncated: bool             # True if we stopped at ROW_CAP
    summary: dict | None        # populated when rows omitted
    next_cursor: str | None     # opaque; pass back to paginate
    export_id: str | None       # pass to export_csv() for large results
```

Rules:
- If `row_count <= INLINE_ROW_THRESHOLD` (default 50), populate `rows`.
- Otherwise, populate `summary` (counts, distinct top-K per column, min/max on numeric/date columns) and `export_id`. Leave `rows` empty.
- Always populate `columns` — the LLM needs the shape even when rows are omitted.

`export_csv(export_id)` writes to `./exports/{export_id}.csv` and returns the path. Don't stream CSVs through MCP tool results.

## Audit log

Every tool call appends one JSON line to `./audit/queries.jsonl`:

```json
{"ts":"2026-04-20T14:03:11Z","tool":"run_query","sql":"SELECT ...","row_count":42,"truncated":false,"user":"stdio","duration_ms":81}
```

Never log secrets or raw row contents.

## Verification checklist

Before declaring M3 complete, all of these must pass (add as integration tests — see [mcp-testing](../mcp-testing/SKILL.md)):

1. `run_query("DROP TABLE employees")` → rejected at parser layer.
2. `run_query("SELECT * FROM employees")` → rejected (raw table not in allowlist; PII view `v_employees_safe` is).
3. `run_query("SELECT * FROM v_employees_safe")` → succeeds with injected `LIMIT 1000`.
4. `run_query` of a 10k-row query → returns `summary + export_id`, `rows == []`, `truncated: true`.
5. An `INSERT` issued via raw psycopg under `mcp_readonly` DSN fails at the DB layer (proves role setup).
6. Audit log contains one entry per call with no raw rows leaked.

## Anti-patterns

- Don't rely on parser-only validation — the DB role is the ultimate safety net.
- Don't accept a DSN, credentials, or a schema name from tool args.
- Don't inline large result sets into tool output — always summarize + export.
- Don't log row contents, even "just for debugging."
- Don't add a curated tool that takes free-form SQL as an argument; that defeats the point.
- Don't GRANT SELECT on raw PII tables — only on masked views.
