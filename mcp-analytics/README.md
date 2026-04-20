# mcp-analytics — M3

Read-only natural-language analytics MCP over the Postgres database from [M1](../springboot-api). Implements the [`readonly-sql-mcp`](../.claude/skills/readonly-sql-mcp/SKILL.md) playbook.

> **This is the highest-risk surface in the project.** All four defense layers from the skill are present — DB role, connection, parser, execution. See §Guardrails below.

## Tools

### Curated (prefer these)

| Tool | Purpose |
|---|---|
| `list_tables()` | Returns the view allowlist. |
| `describe_table(name)` | Columns + types + approximate row count. |
| `get_row_count(table)` | Count rows in an allowlisted view. |
| `recent_employees(days=7)` | Employees joined in the last N days. |
| `orders_by_status(status)` | Orders filtered by `PENDING` / `SHIPPED` / `CANCELLED`. |
| `inactive_users(days=30)` | Customers with no orders in the last N days. |

### Free-form (gated by the 4-layer pipeline)

| Tool | Purpose |
|---|---|
| `run_query(sql)` | Validate → inject `LIMIT` → `EXPLAIN` → execute → audit → summarize. |
| `export_csv(export_id)` | Return the path to a CSV written during a prior large-result query. |

## Guardrails — four layers, all enforced

1. **Database layer.** DSN connects as `mcp_readonly`, a `NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT` role with `SELECT` only on allowlisted views. Created by the springboot-api V2 migration.
2. **Connection layer.** Pool acquires `SET default_transaction_read_only = on; SET statement_timeout = '5s';` on every connection. Belt-and-suspenders over the role defaults.
3. **Parser layer.** `sqlglot` rejects anything that isn't a single `SELECT`, anything that touches a non-allowlisted relation, or anything with DML/DDL nodes.
4. **Execution layer.** Missing / oversized `LIMIT` injected (cap 1000). `EXPLAIN (FORMAT JSON)` runs first; plans with total cost > `MAX_PLAN_COST` are rejected. Statement timeout 5 s. Row cap enforced on fetch.

If any layer is missing, the skill has not been followed.

## Pagination + large-result shape

Every data-returning tool returns:

```json
{
  "columns": ["..."],
  "rows": [],                // populated only when row_count <= INLINE_ROW_THRESHOLD
  "row_count": 240,
  "truncated": false,
  "summary": { ... },        // counts / min / max / top-K — populated when rows omitted
  "export_id": "abc123",     // pass to export_csv() for full data
  "next_cursor": null        // reserved for v2
}
```

Large results are **never** dumped inline — they're summarized plus written to `./exports/{export_id}.csv`.

## Audit log

Every tool call appends one JSON line to `./audit/queries.jsonl`:

```
{"ts":"2026-04-20T14:03:11Z","tool":"run_query","sql":"SELECT ...","row_count":42,"truncated":false,"duration_ms":81}
```

No secrets. No raw row contents.

## Install & run

Requires Python 3.11+ and a running Postgres with the `mcp_readonly` role (i.e. M1's `docker compose up` plus the V2 migration).

```bash
cd mcp-analytics
cp .env.example .env     # edit DB_URL to use mcp_readonly

python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest                   # unit tests

# Interactive
mcp dev src/mcp_analytics/server.py

# stdio for Claude Desktop
mcp-analytics
```

## Integration tests (Docker required)

```bash
pip install -e '.[integration]'
pytest -m integration
```

These spin up a throwaway Postgres via `testcontainers`, apply minimal schema + the `mcp_readonly` role, and assert **every guardrail from PRD §7**, including:

- A raw `INSERT` under `mcp_readonly` fails with a permission error.
- `run_query("SELECT * FROM employees")` is rejected (raw table not in allowlist).
- `run_query("DROP TABLE employees")` is rejected at the parser layer.
- Large-result queries return `summary + export_id`, not inline rows.
- Audit log contains one entry per call with no raw row contents.

## Wire into Claude Desktop

```json
{
  "mcpServers": {
    "analytics": {
      "command": "mcp-analytics",
      "env": {
        "DB_URL": "postgresql://mcp_readonly:mcp_readonly_change_me@localhost:5432/appdb",
        "TABLE_ALLOWLIST": "v_employees_safe,v_orders_safe"
      }
    }
  }
}
```

## M3 exit checklist

- [ ] Unit tests green: `pytest`.
- [ ] Integration tests green: `pytest -m integration`.
- [ ] `INSERT` as `mcp_readonly` via `psql` fails with permission error.
- [ ] `run_query("SELECT * FROM v_employees_safe")` succeeds with injected `LIMIT`.
- [ ] `run_query("SELECT * FROM employees")` is rejected (not allowlisted).
- [ ] `run_query("UPDATE ... ")` is rejected at parser.
- [ ] A 10k-row query returns `summary + export_id`, `rows == []`.
- [ ] `audit/queries.jsonl` gains one entry per call, no row leakage.
