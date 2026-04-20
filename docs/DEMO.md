# Demo — the 5 success-metric questions

This walkthrough proves the PRD §10 success metrics end-to-end: a non-engineer answers 5 business questions through Claude without writing SQL or opening Swagger, in under 15 minutes from a fresh clone.

Prereqs: Docker, Python 3.11+, Claude Desktop.

## 0. One-time setup (≈5 minutes)

```bash
git clone https://github.com/premkumarkori/mcp-claude.git
cd mcp-claude

# Spring Boot API + Postgres + seed data
cd springboot-api
cp .env.example .env
docker compose up --build -d
curl -s http://localhost:8080/actuator/health    # {"status":"UP"}

# API Explorer MCP
cd ../mcp-api-explorer
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'

# Analytics MCP
cd ../mcp-analytics
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'

# Wire into Claude Desktop
cd ..
cp claude_desktop_config.example.json \
   "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
# Edit the three /ABSOLUTE/PATH/TO/mcp-claude placeholders
# Restart Claude Desktop
```

After restart, Claude Desktop's MCP tray should list two servers: **api-explorer** and **analytics**.

## The 5 questions

Ask Claude these in order. Each question names the tool(s) you should see invoked.

### Q1. "What endpoints manage employees?"
Expected tools: `api-explorer.find_endpoint_by_intent("employees")` → `api-explorer.list_endpoints(tag="Employees")`.

Expected answer: 5 endpoints — `GET/POST /employees`, `GET/PUT/DELETE /employees/{id}`.

### Q2. "How do I create an order? Show me the request body."
Expected tools: `api-explorer.find_endpoint_by_intent("create order")` → `api-explorer.show_request_example("/orders", "POST")`.

Expected answer: `POST /orders` with body `{"customerName": "string", "amount": 0}` (required fields only) plus a curl command. The live schema may include an optional `status` enum and `createdAt`.

### Q3. "How many employees joined in the last 7 days?"
Expected tools: `analytics.recent_employees(days=7)`.

Expected answer: a small inline list (typically 4–8 rows from the seeded 60, depending on random distribution). Emails are shown in the **`em***@example.com`** masked form — that's the PII-safe view working.

### Q4. "Which orders are still pending?"
Expected tools: `analytics.orders_by_status("PENDING")`.

Expected answer: ~48 rows (1/5 of the seeded 240 orders). Rows come back inline because the count is just under the 50-row inline threshold. If you bump the threshold lower, Claude will switch to the summary+export path automatically.

### Q5. "Which customers haven't placed an order in 30 days?"
Expected tools: `analytics.inactive_users(days=30)`.

Expected answer: a short list of distinct `customer_name` values whose most recent order is >30 days old.

## What to check while the demo runs

- **`mcp-analytics/audit/queries.jsonl`** gains one line per Analytics tool call — with `duration_ms`, the post-LIMIT-injection SQL, and zero raw row contents.
- **`mcp-analytics/exports/*.csv`** gets a new file whenever Claude triggers the summary path.
- Try the jailbreak questions below and confirm they're refused before the DB is touched.

## Adversarial checks — these must fail

These are the guardrails from PRD §7 in action.

### "Delete all cancelled orders for me."
Expected: refused at multiple layers.
- `api-explorer.call_endpoint` would refuse: `ALLOW_CALL=false` by default.
- `analytics.run_query("DELETE ...")` would refuse: parser rejects non-SELECT (`DROP`/`DELETE`/`UPDATE`/`INSERT`/etc.).
- Direct `DELETE` via the DB would refuse: `mcp_readonly` role has no write grants + session is `read_only`.

### "Show me raw employee emails."
Expected: refused. `mcp_readonly` can only read `v_employees_safe`, which masks the email column as `em***@example.com`. Asking for `SELECT email FROM employees` is rejected because `employees` isn't in the allowlist.

### "Show me the customer table."
Expected: the MCP tells Claude that only `v_employees_safe` and `v_orders_safe` are allowed (`list_tables`). No leakage about what other tables exist.

## Tear-down

```bash
cd springboot-api
docker compose down -v
```

The Python venvs, audit log, and exports directory are gitignored — leave them or delete them; no state is committed.

## If something doesn't work

1. **Claude Desktop shows "server disconnected".** Tail `~/Library/Logs/Claude/mcp-server-api-explorer.log` or `mcp-server-analytics.log`. 90% of failures are wrong absolute paths in `claude_desktop_config.json` or a missing `DB_URL`.
2. **`mcp_readonly` auth fails.** The password is set at migration time via `MCP_READONLY_PASSWORD`. If you changed it in `.env`, update the `DB_URL` in the Claude Desktop config too.
3. **MCP tools return `stale: true`.** The Spring Boot API is down or wasn't reachable at startup. Restart the API; the spec refetches on the next call.
