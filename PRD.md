# PRD — Conversational MCP Layer for a Spring Boot + PostgreSQL CRUD API

**Status:** Draft v1
**Owner:** @koripremkumar
**Last updated:** 2026-04-20

---

## 1. Overview

Build two Model Context Protocol (MCP) servers that sit on top of a Spring Boot + PostgreSQL CRUD API and let internal users — engineers, analysts, and product/ops — ask questions about the **API** and the **data** in natural language through an MCP client (Claude Desktop / Claude Code).

The MCP layer is a **natural-language surface**, not a replacement for OpenAPI/Swagger. Swagger remains the canonical API contract; the MCP servers make the API and the database **discoverable and usable** without requiring the user to read specs or write SQL.

---

## 2. Problem & Motivation

- **Swagger is only discoverable if you already know what you're looking for.** New teammates and non-engineers struggle to answer "does an endpoint exist for X?" without scrolling endless endpoint lists.
- **Database access requires SQL literacy.** Questions like "which employees joined in the last 7 days?" or "which customers haven't placed an order in 30 days?" block on an engineer.
- **Unrestricted AI-generated SQL against a real database is dangerous.** A naive "chat-to-SQL" bot can `DROP`, `UPDATE`, or leak PII.

The MCP protocol gives us a structured way to expose **tools**, **resources**, and **prompts** to an LLM — with typed schemas, auth boundaries, and per-tool guardrails — so we can deliver the conversational UX safely.

---

## 3. Goals / Non-Goals

### Goals (v1)
- Conversational discovery of API endpoints from the Spring Boot app's OpenAPI spec.
- Safe, read-only natural-language access to the PostgreSQL database with hard guardrails (allowlist, row caps, audit log).
- Reusable patterns (skills + templates) so adding a new MCP server in this repo takes hours, not days.
- Local-first demo: everything runs with `docker-compose` + Claude Desktop.

### Non-Goals (v1)
- Arbitrary `UPDATE` / `DELETE` via natural language.
- Production database access.
- Multi-tenant auth / RBAC.
- Replacing Swagger as the canonical API contract.
- Deploying the MCP servers as hosted/remote services.

---

## 4. Users & Personas

| Persona | Needs | Example question |
|---|---|---|
| **Backend dev (new to repo)** | Discover endpoints fast, see request/response shapes. | "What endpoints do we have for employee management?" |
| **Internal analyst** | Ad-hoc data pulls without bothering engineering. | "How many orders were placed in the last 30 days, grouped by status?" |
| **Product / ops** | Answer business questions themselves. | "Which customers haven't placed an order in 30 days?" |

---

## 5. System Architecture

```
┌──────────────────────────┐
│ Claude Desktop /         │
│ Claude Code (MCP client) │
└──────┬────────────┬──────┘
       │ stdio      │ stdio
       ▼            ▼
┌──────────────┐  ┌─────────────────┐
│ API Explorer │  │ Analytics MCP   │
│ MCP (Python) │  │ (Python)        │
└──────┬───────┘  └────────┬────────┘
       │ HTTP              │ SQL (read-only role)
       │ /v3/api-docs      │
       ▼                   ▼
┌──────────────────────────────────┐
│  Spring Boot API  │  PostgreSQL  │
│  (JPA + Flyway)   │              │
└──────────────────────────────────┘
```

- **Spring Boot API** exposes CRUD endpoints and its OpenAPI JSON at `/v3/api-docs`.
- **API Explorer MCP** (Python, stdio) fetches the OpenAPI spec at startup, caches it, and exposes discovery tools + optional `call_endpoint`.
- **Analytics MCP** (Python, stdio) connects to Postgres with a **dedicated read-only role** and exposes curated + validated-SQL tools.
- Both MCP servers are wired into Claude Desktop via `claude_desktop_config.json`.

---

## 6. Scope — v1

### 6.1 Spring Boot Sample API
- Entities: `Employee`, `Order` (or similar — decided during M1).
- Standard CRUD + common filter endpoints (`GET /employees?joinedAfter=...`, `GET /orders?status=...`).
- Stack: Spring Boot 3.x, Spring Web, Spring Data JPA, PostgreSQL driver, Flyway, springdoc-openapi.
- OpenAPI JSON at `/v3/api-docs`, UI at `/swagger-ui.html`.
- Seed data via Flyway so the Analytics MCP has meaningful rows to query.
- Health endpoint at `/actuator/health`.

### 6.2 API Explorer MCP
Tools:
- `list_endpoints(tag?, method?)` — returns a compact list.
- `get_endpoint_details(path, method)` — path params, query params, request/response schemas.
- `find_endpoint_by_intent(query)` — keyword + tag match (not LLM-generated); returns top-N candidates.
- `show_request_example(path, method)` — curl + JSON example derived from the spec.
- `call_endpoint(path, method, params, body)` — **gated by `ALLOW_CALL=true`**, `GET`-only by default, dev/staging base URL allowlist only.

Resources:
- `openapi://paths/{path}/{method}` — one resource per endpoint for context loading.

### 6.3 Analytics MCP
Tools:
- `list_tables()` — allowlisted tables/views only.
- `describe_table(name)` — columns, types, sample row count.
- `get_row_count(table, filters?)`.
- `run_query(sql)` — validated; `SELECT`-only; allowlist-checked; forced `LIMIT`.
- Curated tools (preferred over free-form SQL):
  - `recent_employees(days)`
  - `orders_by_status(status)`
  - `inactive_users(days)`
- `export_csv(query_id)` — returns a file path for results above the inline threshold.

---

## 7. Guardrails (Critical)

These are **non-negotiable** for v1:

1. **Dedicated read-only Postgres role** for the Analytics MCP — `NOSUPERUSER NOCREATEDB NOCREATEROLE`, `GRANT SELECT` only on allowlisted objects. No write/DDL privileges at the DB level, regardless of what the MCP code does.
2. **Table/view allowlist.** Analytics MCP rejects queries referencing any object outside the allowlist. Prefer **PII-masked views** (e.g., `v_employees_safe`) over raw tables.
3. **`SELECT`-only SQL parser check** (using `sqlglot`). Anything that isn't a single `SELECT` is rejected before it reaches the DB.
4. **Row cap.** Hard `LIMIT <= 1000`; injected if missing. Results above an inline threshold (e.g., 50 rows) return a **summary + pagination cursor**, or are offered as a CSV export — never dumped inline.
5. **Query plan sanity check.** `EXPLAIN` every query; reject plans with cartesian joins or seq scans over N rows (configurable).
6. **Audit log.** Every tool invocation writes `(ts, tool, sql/args, row_count, user)` to an append-only log (local file for v1, table for v2).
7. **API Explorer `call_endpoint` is disabled by default.** Requires `ALLOW_CALL=true` env flag, restricted to `GET` verbs and a dev/staging base URL allowlist.
8. **No secrets in logs, no raw result rows in logs.** Structured logging with redaction.

---

## 8. Out-of-Scope / v2

- Admin mutations MCP (`UPDATE` / `DELETE` behind narrow, typed tools + user confirmation).
- Role-based access per MCP client identity.
- Approval workflow for destructive operations.
- Fine-grained audit UI.
- Remote/hosted MCP deployment (HTTP transport + OAuth).

---

## 9. Milestones

| ID | Deliverable | Exit criteria |
|---|---|---|
| **M1** | Spring Boot CRUD + Postgres + OpenAPI running locally. | `docker-compose up` serves CRUD; `/v3/api-docs` returns a valid spec; Flyway seed data present. |
| **M2** | API Explorer MCP connected to Claude Desktop. | Claude can answer "list all endpoints for X" and "show me the request body for Y" end-to-end. |
| **M3** | Read-only Analytics MCP with full guardrails. | All guardrails from §7 pass integration tests (testcontainers). Claude can answer 3 sample business questions. |
| **M4** | End-to-end demo + README. | A new user can clone, `docker-compose up`, wire into Claude Desktop, and answer the 5 success-metric questions in under 15 minutes. |

---

## 10. Success Metrics

- A non-engineer can answer **5 sample business questions** via Claude without writing SQL or opening Swagger:
  1. "What endpoints manage employees?"
  2. "How do I create an order?"
  3. "How many employees joined in the last 7 days?"
  4. "Which orders are still pending?"
  5. "Which customers haven't placed an order in 30 days?"
- **Zero** tool invocations in the audit log that wrote data, ran DDL, or queried a non-allowlisted table. (This is the safety SLO — a single violation fails the milestone.)
- Setup-to-first-answer time under 15 minutes for a new clone.

---

## 11. Open Questions

- **Auth model.** Stay stdio-only (single user, local) for v1, or add HTTP + OAuth early to make multi-user paths easier?
- **Hosting.** Keep local-only, or target a team-shared deployment in v2? Affects secrets strategy.
- **Large-result export.** CSV file on disk vs. signed URL vs. inline-with-pagination. Leaning file-on-disk for v1 simplicity.
- **Curated vs. free-form SQL balance.** How many curated tools before we're just rebuilding the API? Revisit after M3 with usage data.
- **PII policy.** Which columns are masked in v1 views? Needs a one-page PII classification doc before M3.
