# Test Results — 2026-04-20

Captured during M4. Everything below was run in the repo's current state on macOS (Darwin 25.4.0), Python 3.11.4, Java 21.0.3, Docker 29.3.1, Postgres 16.

## Summary

| Scope | Result | Count | Duration |
|---|---|---|---|
| mcp-api-explorer unit | ✅ pass | 21 | 0.23 s |
| mcp-analytics unit | ✅ pass | 44 (+1 skipped) | 0.17 s |
| mcp-analytics integration (testcontainers) | ✅ pass | 5 | 2.05 s |
| springboot-api `mvn -DskipTests package` | ✅ pass | — | 30.6 s |
| End-to-end smoke (docker compose + live curl + MCP calls) | ✅ pass | — | ≈ 45 s |
| **Total automated assertions** | **✅** | **70** | — |

No known failures. One item flagged as follow-up: the Spring Boot app has **no unit tests yet** — `mvn test` reports "No tests to run". Adding a `@SpringBootTest` context-load smoke test is a cheap follow-up.

## Unit tests — mcp-api-explorer

Command:
```bash
cd mcp-api-explorer && .venv/bin/pytest -v
```

Output:
```
platform darwin -- Python 3.11.4, pytest-9.0.3, pluggy-1.6.0
plugins: asyncio-1.3.0, respx-0.23.1, anyio-4.13.0
collected 21 items

tests/unit/test_caller.py .....                    [ 23%]
tests/unit/test_examples.py .......                [ 57%]
tests/unit/test_intent.py .....                    [ 80%]
tests/unit/test_spec.py ....                       [100%]

============================== 21 passed in 0.23s ==============================
```

Coverage map (by source file → test assertions):
- `spec.py` — fetch ok + TTL cache hit + stale-on-500 fallback + operation summarization.
- `intent.py` — "create order" ranks POST /orders first; "list employees" prefers GET; "delete" ranks DELETE verb first; empty query returns `[]`; `limit` respected.
- `examples.py` — primitive placeholders; `example` > `default` > `enum` precedence; required-only object fields; path param substitution; raises on unknown endpoint.
- `caller.py` — refused by default; refused for off-allowlist URL; refused for mutating verb without flag; allowed GET returns status+body preview; allowed POST when both flags on.

## Unit tests — mcp-analytics

Command:
```bash
cd mcp-analytics && .venv/bin/pytest -v
```

Output:
```
platform darwin -- Python 3.11.4, pytest-9.0.3, pluggy-1.6.0
plugins: asyncio-1.3.0, anyio-4.13.0
collected 44 items / 1 skipped

tests/unit/test_audit.py ...                       [  6%]
tests/unit/test_config.py ...                      [ 13%]
tests/unit/test_export.py .........                [ 34%]
tests/unit/test_guardrails.py ........             [ 52%]
tests/unit/test_pagination.py .....                [ 63%]
tests/unit/test_validator.py ................      [100%]

======================== 44 passed, 1 skipped in 0.17s =========================
```

(1 skipped = the whole `tests/integration/` module — pytest collects but defers to `-m integration`.)

Coverage map:
- `validator.py` — accepts SELECT + joined SELECT over allowlist; rejects `DROP`/`TRUNCATE`/`UPDATE`/`DELETE`/`INSERT`/`CREATE`/`ALTER`; rejects raw `employees`; rejects mixed allowlisted+raw join; rejects multi-statement; rejects empty / invalid SQL; rejects data-modifying CTEs (`WITH x AS (DELETE ...)`).
- `guardrails.py` — LIMIT injection when missing; cap oversized LIMIT; preserve smaller LIMIT; reject non-positive cap; extract plan cost from dict row + JSON string; plan-too-expensive rejection.
- `pagination.py` — Decimal and datetime coercion; numeric min/max + top-K strings; null counts; inline-vs-summary routing.
- `audit.py` — JSONL append; no rows leaked; auto-creates parent dir.
- `export.py` — write/resolve roundtrip; path-traversal rejection (`../`, absolute, slashes, empty); missing-file error; random export ids.
- `config.py` — CSV env var parsing with `NoDecode`; case normalization; default DSN uses `mcp_readonly`.

## Integration tests — mcp-analytics

Command:
```bash
cd mcp-analytics && .venv/bin/pip install -e '.[integration]' && .venv/bin/pytest -v -m integration
```

Output:
```
platform darwin -- Python 3.11.4
collected 49 items / 44 deselected / 5 selected

tests/integration/test_guardrails_live.py .....    [100%]

======================= 5 passed, 44 deselected in 2.05s =======================
```

These are the **PRD §7 guardrails proven against a real Postgres**:

| Test | What it proves |
|---|---|
| `test_readonly_role_blocks_insert` | Layer 1/2: DB itself rejects `INSERT` for `mcp_readonly` (either `InsufficientPrivilegeError` or `ReadOnlySQLTransactionError` — in practice the read-only transaction fires first). |
| `test_raw_table_access_refused` | Layer 3: parser rejects `SELECT * FROM employees` (raw table not in allowlist). |
| `test_dml_refused_at_parser` | Layer 3: parser rejects `DROP TABLE employees`. |
| `test_large_result_returns_summary_and_export` | Layer 4 + pagination: 120-row query returns `summary + export_id`, `rows == []`, CSV file present on disk. |
| `test_audit_log_has_entry_per_call_no_rows_leaked` | Audit log contains one entry per call with the post-LIMIT SQL; grep for `@x.com` returns 0 matches. |

### One subtle finding worth recording

The initial `test_readonly_role_blocks_insert` asserted `asyncpg.InsufficientPrivilegeError`, but the live container actually raised `asyncpg.ReadOnlySQLTransactionError`. Both are guardrails we rely on — the read-only transaction setting (applied via `ALTER ROLE ... SET default_transaction_read_only = on`) fires *before* the per-object privilege check. The test was updated to accept either, and a comment was left in-file explaining the ordering. In production you want both layers anyway; losing one should not silently re-enable writes.

## Spring Boot build

Command:
```bash
cd springboot-api && mvn -B -DskipTests package
```

Result:
```
[INFO] BUILD SUCCESS
[INFO] Total time:  30.6 s
```

Produced `target/mcp-sample-api-0.1.0.jar` (56 MB fat jar). No unit tests exist on this side yet — noted as a follow-up.

## End-to-end smoke test

Ran `docker compose up --build -d` in `springboot-api/`, then exercised both MCP servers against the live stack, then tore everything down with `docker compose down -v`.

### Spring Boot API

```
=== /actuator/health ===
{"status": "UP"}

=== /v3/api-docs paths ===
[
  "/employees",
  "/employees/{id}",
  "/orders",
  "/orders/{id}"
]

=== /v3/api-docs tags ===
['Employees', 'Orders']
```

Seed data loaded as expected:
- `GET /employees` returned 60 rows.
- `GET /orders?status=PENDING` returned 48 rows.
- Sample employee record shows `email: "employee1@example.com"` (raw email visible through the API; masking happens in the view for the Analytics MCP).

### `mcp_readonly` Postgres role — live verification

| Command | Result | Interpretation |
|---|---|---|
| `SELECT COUNT(*) FROM v_employees_safe` as `mcp_readonly` | `60` | Allowlisted view readable. |
| `INSERT INTO employees(...) VALUES (...)` as `mcp_readonly` | `ERROR: cannot execute INSERT in a read-only transaction` | Layer 2 (session read-only) blocks the write. |
| `SELECT * FROM employees` as `mcp_readonly` | `ERROR: permission denied for table employees` | Layer 1 (no `GRANT SELECT`) blocks raw-table access. |

### API Explorer MCP against the live API

```
list_endpoints: count=10, stale=False
  paths: all 10 CRUD endpoints (DELETE/GET/POST/PUT across /employees and /orders)

find_endpoint_by_intent('create order'):
  score= 25  POST   /orders
  score= 15  POST   /employees
  score= 10  DELETE /orders/{id}

show_request_example('/orders','POST'):
  url: http://localhost:8080/orders
  body: {"customerName": "string", "amount": 0}

call_endpoint_tool (default, ALLOW_CALL=false):
  refused=True, reason='call_endpoint is disabled. Set ALLOW_CALL=true to enable (PRD §7).'
```

### Analytics MCP against the live DB

```
=== list_tables ===
{'tables': ['v_employees_safe', 'v_orders_safe']}

=== describe_table('v_employees_safe') ===
  {'column_name': 'id',           'data_type': 'bigint',                     'is_nullable': 'YES'}
  {'column_name': 'name',         'data_type': 'text',                       'is_nullable': 'YES'}
  {'column_name': 'email_masked', 'data_type': 'text',                       'is_nullable': 'YES'}   ← PII masking visible in the view
  {'column_name': 'joined_at',    'data_type': 'timestamp with time zone',   'is_nullable': 'YES'}

=== get_row_count('v_orders_safe') ===
{'rows': [{'count': 240}], 'row_count': 1}

=== recent_employees(days=7) ===
row_count=7, truncated=False
  sample: {'id': 9, 'name': 'Employee 9', 'email_masked': 'em***@example.com', ...}
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                          masking confirmed end-to-end

=== orders_by_status('PENDING') ===
row_count=48, inline (under 50-row threshold)

=== run_query — DROP TABLE (must be refused) ===
  REFUSED: SqlValidationError: Only SELECT queries are allowed (got Drop).

=== run_query — SELECT * FROM employees (must be refused) ===
  REFUSED: SqlValidationError: Table or view 'employees' is not in the allowlist.

=== run_query — SELECT id, customer_name FROM v_orders_safe WHERE amount > 500 ===
row_count=118, summary=present, rows=[] (large-result path)

=== export_csv('335093ad28100925') ===
  path=/tmp/mcp_smoke_exports/335093ad28100925.csv, size_bytes=1939
  first 5 lines:
    id,customer_name
    1,Customer 2
    5,Customer 6
    7,Customer 8
    12,Customer 13
```

### Audit log

7 entries for the session, one per tool call:
- `describe_table` (no SQL — used `information_schema` directly)
- `get_row_count`, `recent_employees`, `orders_by_status`, `run_query` (×3) — all with post-`LIMIT`-injection SQL logged (`LIMIT 1001`).
- Rejected calls (`DROP TABLE v_employees_safe`, `SELECT * FROM employees`) logged with their error and the original attempted SQL.
- **PII leakage check:** `grep '@example' queries.jsonl` → 0 matches. `"rows"` never appears. Audit log is clean.

Small observation — `list_tables` is the one tool that does **not** audit (it's a pure-config lookup that doesn't touch the DB). That's fine per the skill's "audit every DB-touching call" intent, but worth noting if you ever want a 1:1 tool-invocation:audit-line mapping.

## How to reproduce

```bash
# Unit tests
cd mcp-api-explorer && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/pytest
cd ../mcp-analytics   && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/pytest

# Integration tests (Docker required)
cd mcp-analytics && .venv/bin/pip install -e '.[integration]' && .venv/bin/pytest -m integration

# Spring Boot build
cd springboot-api && mvn -B -DskipTests package

# End-to-end — see docs/DEMO.md for the full walkthrough including Claude Desktop
cd springboot-api && cp .env.example .env && docker compose up --build -d
curl -s http://localhost:8080/actuator/health
docker compose down -v
```
