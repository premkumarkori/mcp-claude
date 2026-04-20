---
name: python-mcp-server
description: Use when building, extending, or debugging a Python MCP server in this repo (API Explorer, Analytics, or any future MCP). Triggers on "create an MCP server", "add a tool to the MCP", "wire into Claude Desktop", or work inside mcp-*/.
---

# python-mcp-server

**Trigger:** any request to create or modify a Python MCP server under `mcp-*/`. This is the **foundation skill** — the `openapi-to-mcp` and `readonly-sql-mcp` skills both build on it.

## SDK choice (fixed)

- **`mcp` Python SDK** (`pip install mcp`), FastMCP-style decorators.
- **stdio transport** for all v1 servers (Claude Desktop local). HTTP is v2.
- **Pydantic v2** for tool input/output schemas.
- **`pydantic-settings`** for env-var config.

Do not pull in alternate MCP libraries; keep the stack uniform across `mcp-*/` servers.

## Project layout

```
mcp-<name>/
├── pyproject.toml
├── .env.example            # committed; real .env is gitignored
├── README.md               # how to run + wire into Claude Desktop
├── src/
│   └── mcp_<name>/
│       ├── __init__.py
│       ├── server.py       # FastMCP() + @mcp.tool definitions
│       ├── config.py       # Settings(BaseSettings)
│       ├── tools/          # one module per logical tool group
│       └── logging.py      # structured logger with redaction
└── tests/
    ├── unit/
    └── integration/
```

Every server must have a `README.md` showing `uv run mcp dev src/mcp_<name>/server.py` and the Claude Desktop config snippet.

## Skeleton (`server.py`)

```python
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from .config import settings
from .logging import logger

mcp = FastMCP("api-explorer")  # name appears in Claude Desktop

class ListEndpointsArgs(BaseModel):
    tag: str | None = Field(None, description="Filter by OpenAPI tag")
    method: str | None = Field(None, description="HTTP method filter")

@mcp.tool()
def list_endpoints(args: ListEndpointsArgs) -> list[dict]:
    """List available API endpoints, optionally filtered by tag or method."""
    logger.info("tool.list_endpoints", tag=args.tag, method=args.method)
    ...

if __name__ == "__main__":
    mcp.run()  # stdio by default
```

Rules:
- **Every tool takes a single Pydantic model** as input. No positional args, no kwargs sprawl.
- **Every tool has a one-line docstring** — it becomes the tool description shown to the LLM. Write it for the LLM, not for humans.
- **Every tool logs its name + non-sensitive args on entry.** Never log secrets, full result rows, or PII.

## Config (`config.py`)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API Explorer
    api_base_url: str = "http://localhost:8080"
    openapi_path: str = "/v3/api-docs"
    allow_call: bool = False
    call_base_url_allowlist: list[str] = ["http://localhost:8080"]

    # Analytics
    db_url: str | None = None          # postgresql://mcp_readonly:...@host/db
    table_allowlist: list[str] = []
    row_cap: int = 1000
    inline_row_threshold: int = 50

settings = Settings()
```

**All config comes from env vars.** No hardcoded URLs, no hardcoded credentials, ever.

## Logging (`logging.py`)

- Use `structlog` or stdlib `logging` with a JSON formatter.
- **Redact** anything matching `password`, `token`, `secret`, `api_key` keys.
- Never log raw result rows from the DB or API bodies larger than 1 KB — log a `row_count` / `size_bytes` summary instead.
- Log destination: stderr (stdout is reserved for MCP stdio protocol).

## Tool design rules

1. **Curated > free-form.** If you can name a tool `recent_employees(days)`, do that instead of expecting the LLM to compose SQL or URLs.
2. **Inputs are typed and narrow.** Use `Literal["pending", "shipped", "cancelled"]` instead of `str` when the domain is closed.
3. **Outputs are structured and small.** Prefer `{summary, rows, next_cursor}` over dumping a list. See `readonly-sql-mcp` for the pagination shape.
4. **Fail loudly but safely.** Raise a descriptive error the LLM can act on ("table X not in allowlist") — never leak stack traces, DB internals, or auth headers.
5. **Idempotency.** v1 tools are read-only; assume they may be retried.

## Wiring into Claude Desktop

In `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "api-explorer": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/mcp-api-explorer", "mcp-api-explorer"],
      "env": {
        "API_BASE_URL": "http://localhost:8080"
      }
    }
  }
}
```

Restart Claude Desktop after edits. If the server fails to start, Claude Desktop swallows the error — tail `~/Library/Logs/Claude/mcp-server-*.log`.

## Verification before moving on

- `uv run mcp dev src/mcp_<name>/server.py` opens the Inspector; every tool appears with a correct schema.
- Unit tests cover: (a) each tool's happy path, (b) each guardrail rejection path, (c) config parsing.
- See [mcp-testing](../mcp-testing/SKILL.md) for the full test playbook.

## Anti-patterns

- Don't print to stdout — it corrupts the stdio protocol. Use the logger (stderr).
- Don't accept free-form `**kwargs` in tools — the LLM will send garbage. Validate with Pydantic.
- Don't catch-and-swallow errors silently; the LLM needs the error message to recover.
- Don't block the event loop with sync HTTP/DB calls inside async tools. Use `httpx.AsyncClient` and `asyncpg`.
