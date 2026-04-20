# mcp-claude

A learning/side-project exploring the **Model Context Protocol (MCP)** as a natural-language surface on top of a Spring Boot + PostgreSQL CRUD API.

Two MCP servers are planned:

1. **API Explorer MCP** — OpenAPI-backed discovery and safe endpoint calls.
2. **Read-only Analytics MCP** — NL → SQL against allowlisted views, with row caps, pagination, and an audit log.

> MCP is a **natural-language layer** on top of the system — not a replacement for OpenAPI/Swagger. Swagger stays the canonical API contract.

## Status

**Scaffolding only.** No application code yet. The next step is M1 from the PRD.

## Repo layout

```
.
├── PRD.md                          # Product requirements — read this first
├── README.md
├── .gitignore
└── .claude/
    └── skills/
        ├── springboot-api-scaffold/SKILL.md   # M1: Spring Boot CRUD + Postgres
        ├── python-mcp-server/SKILL.md         # foundation for all MCP servers
        ├── openapi-to-mcp/SKILL.md            # M2: API Explorer MCP
        ├── readonly-sql-mcp/SKILL.md          # M3: Analytics MCP (guardrails)
        └── mcp-testing/SKILL.md               # test playbook
```

## Getting started (for contributors)

1. Read [PRD.md](PRD.md) end-to-end — especially §7 (Guardrails) and §9 (Milestones).
2. Open the repo in Claude Code. The skills in `.claude/skills/` auto-register.
3. Ask Claude to scaffold M1: _"scaffold the Spring Boot API per the PRD"_.

## Milestones

| ID | Deliverable |
|---|---|
| **M1** | Spring Boot CRUD + Postgres + OpenAPI running locally |
| **M2** | API Explorer MCP connected to Claude Desktop |
| **M3** | Read-only Analytics MCP with full guardrails |
| **M4** | End-to-end demo + setup instructions |

See the PRD for exit criteria.

## Guardrail principles (non-negotiable)

- Dedicated read-only Postgres role — no DML/DDL at the DB layer.
- Table/view allowlist enforced at the SQL-parser layer.
- Hard `LIMIT` on every query; large results return a summary + CSV export, never inline.
- Every tool call is audit-logged.
- No secrets, no raw result rows in logs.

Full details in [PRD.md §7](PRD.md#7-guardrails-critical) and the [`readonly-sql-mcp`](.claude/skills/readonly-sql-mcp/SKILL.md) skill.
