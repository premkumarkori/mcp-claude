# mcp-api-explorer — M2

Python MCP server that makes the Spring Boot API (from [M1](../springboot-api)) **conversationally discoverable** by reading its OpenAPI spec. Implements the [`openapi-to-mcp`](../.claude/skills/openapi-to-mcp/SKILL.md) playbook.

## Tools

| Tool | Purpose |
|---|---|
| `list_endpoints(tag?, method?)` | Compact list of endpoints. |
| `get_endpoint_details(path, method)` | Full schema for one endpoint. |
| `find_endpoint_by_intent(query)` | Keyword + tag scoring (no LLM). Returns top-5 candidates. |
| `show_request_example(path, method)` | Minimal valid JSON + `curl` derived from the schema. |
| `call_endpoint(path, method, ...)` | **Gated.** Disabled by default. See §Gating below. |
| `refresh_spec()` | Force re-fetch of OpenAPI. |

### Resources

- `openapi://paths/{url-encoded-path}/{method}` — one resource per endpoint.

## Install & run

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) (recommended) or plain `pip`.

```bash
cd mcp-api-explorer
cp .env.example .env

# uv (recommended)
uv sync --extra dev
uv run mcp dev src/mcp_api_explorer/server.py     # MCP Inspector
uv run mcp-api-explorer                            # stdio server

# or pip
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
mcp-api-explorer
```

## Test

```bash
uv run pytest
```

Unit tests cover spec fetch + `$ref` resolution + cache, intent scoring, example synthesis, and every `call_endpoint` gating branch — using a fixture OpenAPI spec under `tests/fixtures/`.

## Wire into Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "api-explorer": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/ABS/PATH/TO/mcp-claude/mcp-api-explorer",
        "mcp-api-explorer"
      ],
      "env": {
        "API_BASE_URL": "http://localhost:8080",
        "OPENAPI_PATH": "/v3/api-docs"
      }
    }
  }
}
```

Restart Claude Desktop. Tail `~/Library/Logs/Claude/mcp-server-api-explorer.log` if the server fails to start.

## Gating (`call_endpoint`)

Default config refuses every live call. To enable:

- `ALLOW_CALL=true` — permits `GET` against `CALL_BASE_URL_ALLOWLIST`.
- `ALLOW_MUTATING_CALLS=true` **and** `ALLOW_CALL=true` — permits `POST/PUT/PATCH/DELETE`.
- Any base URL outside `CALL_BASE_URL_ALLOWLIST` is refused regardless of flags.

Per-PRD §7, never add production base URLs to the allowlist in v1.

## M2 exit checklist

- [ ] `uv run mcp dev src/mcp_api_explorer/server.py` opens Inspector; all tools present with schemas.
- [ ] With the Spring Boot API running, `list_endpoints()` returns 10 endpoints (5 for Employees, 5 for Orders).
- [ ] `find_endpoint_by_intent("create order")` ranks `POST /orders` first.
- [ ] `show_request_example("/orders", "POST")` returns schema-valid JSON.
- [ ] `call_endpoint` refuses when `ALLOW_CALL=false` (default).
- [ ] Wired into Claude Desktop; Claude answers "what endpoints manage employees?" end-to-end.
