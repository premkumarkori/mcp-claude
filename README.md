# mcp-claude

A learning/side-project exploring the **Model Context Protocol (MCP)** as a natural-language surface on top of a Spring Boot + PostgreSQL CRUD API.

Two MCP servers are implemented:

1. **API Explorer MCP** — OpenAPI-backed discovery and safe endpoint calls.
2. **Read-only Analytics MCP** — NL → SQL against allowlisted views, with row caps, pagination, and an audit log.

> MCP is a **natural-language layer** on top of the system — not a replacement for OpenAPI/Swagger. Swagger stays the canonical API contract.

## Status — all four PRD milestones complete

| ID | Deliverable | State |
|---|---|---|
| **M1** | Spring Boot CRUD + Postgres + OpenAPI + Flyway + `mcp_readonly` role | ✅ |
| **M2** | API Explorer MCP (Python, OpenAPI-backed, gated `call_endpoint`) | ✅ |
| **M3** | Read-only Analytics MCP with 4-layer guardrails | ✅ |
| **M4** | End-to-end demo + test results + Claude Desktop config | ✅ |

Latest test run: **21 + 44 + 5 = 70 tests passing**, all guardrails verified end-to-end. See [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md).

## Repo layout

```
.
├── PRD.md                              # Source of truth for scope & guardrails
├── README.md                           # This file
├── claude_desktop_config.example.json  # Paste into ~/Library/.../claude_desktop_config.json
├── docs/
│   ├── DEMO.md                         # 5 success-metric questions, step-by-step
│   └── TEST_RESULTS.md                 # Captured unit + integration + e2e runs
├── springboot-api/                     # M1 — CRUD API (Java 21, Spring Boot 3.3)
├── mcp-api-explorer/                   # M2 — OpenAPI-backed MCP (Python 3.11)
├── mcp-analytics/                      # M3 — read-only SQL MCP (Python 3.11)
└── .claude/skills/                     # Playbooks for future work in this repo
```

## Quick start (15-minute path)

Prereqs: Docker, Python 3.11+, (optional) Claude Desktop.

```bash
# 1. Start Postgres + the API (M1)
cd springboot-api
cp .env.example .env
docker compose up --build -d
curl -s http://localhost:8080/actuator/health   # {"status":"UP"}

# 2. Install the API Explorer MCP (M2)
cd ../mcp-api-explorer
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                                # 21 passed

# 3. Install the Analytics MCP (M3)
cd ../mcp-analytics
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                                # 44 passed

# 4. Wire into Claude Desktop
#    copy claude_desktop_config.example.json -> ~/Library/Application Support/Claude/claude_desktop_config.json
#    edit the two absolute paths, restart Claude Desktop
```

Then walk through the 5 success-metric questions in [docs/DEMO.md](docs/DEMO.md).

## Testing

| Scope | How | Count |
|---|---|---|
| API Explorer unit | `cd mcp-api-explorer && pytest` | 21 |
| Analytics unit | `cd mcp-analytics && pytest` | 44 |
| Analytics integration (needs Docker) | `cd mcp-analytics && pip install -e '.[integration]' && pytest -m integration` | 5 |
| Spring Boot build | `cd springboot-api && mvn -B -DskipTests package` | — |
| End-to-end smoke | [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md) § E2E | — |

All of these ran green on 2026-04-20 — full output captured in the test results doc.

## Guardrail principles (non-negotiable)

Quoted from [PRD.md §7](PRD.md#7-guardrails-critical):

- **Dedicated read-only Postgres role.** `mcp_readonly`, `NOSUPERUSER NOCREATEDB NOCREATEROLE`, `GRANT SELECT` on `v_*_safe` views only.
- **Table/view allowlist enforced at the SQL-parser layer** (`sqlglot`).
- **Hard `LIMIT`** on every query (cap 1000). Large results (>50 rows) return a **summary + CSV export**, never inline.
- **Every tool call is audit-logged** to `mcp-analytics/audit/queries.jsonl` — no raw rows, no secrets.
- **`call_endpoint` is disabled by default**; requires explicit env flags + base-URL allowlist.

These are verified by 5 integration tests against a real Postgres via `testcontainers` — see [docs/TEST_RESULTS.md § Integration tests](docs/TEST_RESULTS.md#integration-tests-mcp-analytics).

## Reading order for contributors

1. [PRD.md](PRD.md) — especially §7 (Guardrails) and §9 (Milestones).
2. [docs/DEMO.md](docs/DEMO.md) — what success looks like.
3. [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md) — what currently works.
4. `.claude/skills/` — playbooks for extending any subsystem.

## License

Personal/educational — no license declared.
