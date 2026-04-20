---
name: mcp-testing
description: Use when testing or debugging a Python MCP server in this repo, before or after wiring it into Claude Desktop. Triggers on "test the MCP", "debug a tool", "run mcp inspector", or adding tests under mcp-*/tests/.
---

# mcp-testing

**Trigger:** any testing or debugging work on an MCP server in this repo. Apply **before** connecting a server to Claude Desktop and whenever a guardrail or tool changes.

## Three test tiers — all required

| Tier | Tool | Purpose |
|---|---|---|
| 1. Interactive | MCP Inspector | Smoke-test tool shape + happy path by hand |
| 2. Unit | `pytest` | Per-tool schema, happy path, every guardrail rejection |
| 3. Integration | `pytest` + `testcontainers` | End-to-end against real Postgres / real OpenAPI fixture |

Do not skip tier 3 for the Analytics MCP — parser-level rejection tests do **not** prove the DB role setup actually blocks writes.

## Tier 1: MCP Inspector

```bash
uv run mcp dev src/mcp_<name>/server.py
```

The Inspector opens a browser UI. Checklist:
- Every tool appears with its name, description, and input schema.
- Input schema shows correct Pydantic types (no bare `object`).
- Invoke each tool at least once with a valid input; confirm output shape.
- Invoke each tool with a deliberately invalid input; confirm a clean error (no stack trace).

Treat this as a **pre-commit check**, not a substitute for automated tests.

## Tier 2: Unit tests (`tests/unit/`)

Structure one test module per tool module. For each tool, cover:

1. **Schema snapshot** — `ToolName.model_json_schema()` matches a committed fixture. Catches accidental arg renames.
2. **Happy path** — mock the external dependency (HTTP client or DB connection) and assert the returned shape.
3. **Each guardrail rejection path** — one test per rejection reason. Examples for `run_query`:
   - non-SELECT → `ValueError`
   - table outside allowlist → `ValueError`
   - DML keyword inside a subquery → `ValueError`
   - `LIMIT` > `ROW_CAP` → injected down to cap
   - missing `LIMIT` → injected at cap
4. **Config parsing** — `Settings()` with a fixture `.env` loads the right values; missing required vars raise.

Use `pytest-asyncio` for async tools. Mock `httpx.AsyncClient` with `respx`, and `asyncpg` with a fake connection object that records the SQL it received.

## Tier 3: Integration tests (`tests/integration/`)

### Analytics MCP

Use `testcontainers[postgresql]`:

```python
@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16") as pg:
        # Apply Flyway migrations (or equivalent) so v_*_safe views exist.
        # Create mcp_readonly role.
        yield pg
```

Must-pass assertions (these mirror PRD §7):
- A raw `INSERT` executed through the `mcp_readonly` DSN **fails** with a permission error. (Proves the DB role, not just the parser.)
- `run_query("SELECT * FROM employees")` is rejected — `employees` is not in the view allowlist.
- `run_query("SELECT * FROM v_employees_safe")` succeeds and the returned `sql` has `LIMIT <= 1000`.
- A query returning > `INLINE_ROW_THRESHOLD` rows returns `summary + export_id`, `rows == []`.
- `export_csv(export_id)` produces a file with the correct row count.
- The audit log gains exactly one entry per tool call; none contain raw row contents.

### API Explorer MCP

Use a **committed OpenAPI fixture** (`tests/fixtures/openapi.json`) served by a throwaway `httpx.MockTransport` or a tiny FastAPI app on a random port. Assertions:
- `list_endpoints` pagination + filters.
- `find_endpoint_by_intent("create order")` ranks `POST /orders` first.
- `show_request_example` produces schema-valid JSON (validate with `jsonschema`).
- `call_endpoint` is refused when `ALLOW_CALL=false`.
- `call_endpoint` refuses a base URL outside the allowlist even when enabled.
- `call_endpoint` refuses `POST` when `ALLOW_MUTATING_CALLS=false`.

## Smoke test before wiring into Claude Desktop

```bash
# From the server directory
uv run mcp dev src/mcp_<name>/server.py    # Inspector loads cleanly
uv run pytest                               # Tiers 2 & 3 green
tail -f ~/Library/Logs/Claude/mcp-server-<name>.log   # After wiring, watch for startup errors
```

If Claude Desktop shows "server disconnected", the process crashed — the log has the traceback. Common causes:
- `print()` to stdout (corrupts stdio protocol).
- Missing env var raising at `Settings()` construction.
- Async function declared but invoked synchronously.

## Reproducing a failing tool call

When a tool misbehaves in Claude Desktop:

1. Copy the tool arguments from the Claude Desktop log.
2. Invoke the same tool with those args in the Inspector (tier 1) — reproduces ~80% of issues.
3. If not reproducible there, write a unit test with those exact args (tier 2).
4. If still not reproducible, the failure is environmental — check env vars, cwd, and DB connectivity.

## Coverage targets (v1)

- Unit: **100% of guardrail branches** in `readonly-sql-mcp`. Line coverage ≥ 85% overall per server.
- Integration: every assertion listed above passes in CI.
- No "flaky" tests allowed. If a test intermittently fails, fix or delete it — silent flakes erode trust in the safety tests.

## Anti-patterns

- Don't mock the DB in the Analytics MCP's safety tests — mocks can't prove `GRANT` worked.
- Don't assert on freeform LLM output; tests should call tool functions directly.
- Don't skip the Inspector pass "because unit tests are green" — Claude Desktop sees the tool schema, not your Python types.
- Don't commit real credentials in test fixtures — use ephemeral testcontainers creds only.
