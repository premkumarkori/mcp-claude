---
name: openapi-to-mcp
description: Use when implementing or extending the API Explorer MCP that reads the Spring Boot OpenAPI spec. Triggers on "build the API Explorer MCP", "add list_endpoints", "add call_endpoint", or work inside mcp-api-explorer/.
---

# openapi-to-mcp

**Trigger:** work on the **API Explorer MCP** (`mcp-api-explorer/`) — the server from [PRD.md](../../../PRD.md) §6.2. Build on top of [python-mcp-server](../python-mcp-server/SKILL.md).

Goal: make the Spring Boot API **conversationally discoverable** without replacing Swagger.

## Source of truth

- OpenAPI JSON fetched from `{API_BASE_URL}{OPENAPI_PATH}` (default `http://localhost:8080/v3/api-docs`).
- **Cache with TTL** (default 60s). Refetch on TTL expiry or on an explicit `refresh_spec()` tool call. Never assume the spec is static — restarts of the API change it.
- If fetch fails, serve the last successful cached version and surface a `stale: true` flag in tool output. Don't hard-fail the MCP server.

## Tools (exactly these for v1)

### `list_endpoints(tag?, method?)`
Returns a compact list: `[{path, method, tag, summary}]`. Sort by tag then path. No request/response schemas here — keep payload small.

### `get_endpoint_details(path, method)`
Full view: path params, query params, request body schema, response schemas per status code, tags, security requirements. This is the "I want to use this endpoint" tool.

### `find_endpoint_by_intent(query)`
**Keyword + tag match, not an LLM call.** Rationale: the LLM calling this tool *is* the reasoning layer — we don't need a second LLM inside the MCP. Implementation:
- Tokenize `query`; lowercase; drop stopwords.
- Score each endpoint by overlap with `{tag, summary, path segments, operationId}`.
- Return top 5 with scores. Let the LLM pick.

### `show_request_example(path, method)`
Synthesize a minimal valid example from the schema:
- Required fields only.
- Use `example` / `default` from the spec when present; otherwise type-appropriate placeholders (`"string"`, `0`, `false`, ISO-8601 timestamp).
- Return both a **curl** command and a **JSON body** string.

### `call_endpoint(path, method, params, body)` — GATED
**Disabled unless `ALLOW_CALL=true`.** Even when enabled:
- Only methods in `{GET}` by default. `POST`/`PUT`/`PATCH`/`DELETE` require `ALLOW_MUTATING_CALLS=true` **and** the base URL must be in `CALL_BASE_URL_ALLOWLIST`.
- Validate request against the OpenAPI schema before sending; reject with a clear error if invalid.
- 10s timeout. Return `{status, headers, body_preview (first 2 KB), body_truncated}`.
- **Never** forward cookies or auth headers from the MCP process environment — accept explicit `headers` arg only, and redact obvious secrets when logging.

## Resources (optional but useful)

Expose one MCP resource per endpoint:
- URI: `openapi://paths/{url-encoded-path}/{method}`
- Content: the `get_endpoint_details` payload as JSON.

Claude Desktop can then load a specific endpoint into context without a tool roundtrip.

## Config (additions to `python-mcp-server` settings)

```python
api_base_url: str = "http://localhost:8080"
openapi_path: str = "/v3/api-docs"
spec_cache_ttl_seconds: int = 60

allow_call: bool = False
allow_mutating_calls: bool = False
call_base_url_allowlist: list[str] = ["http://localhost:8080"]
call_timeout_seconds: float = 10.0
```

All env-driven. Defaults are **safe** — `call_endpoint` off, localhost only.

## Implementation notes

- Use `httpx.AsyncClient` with a shared client instance; set `timeout=10.0`.
- Resolve `$ref` in the spec **once** at fetch time (use `jsonref` or equivalent) so tools don't re-resolve on every call.
- `find_endpoint_by_intent` should be a pure function — easy to unit-test with fixture specs.
- For `call_endpoint`, build the URL with path param substitution; reject if any required path param is missing before making the request.

## Example flows the MCP must handle well

From PRD §10:
- "What endpoints manage employees?" → `find_endpoint_by_intent("employees")` → LLM picks top candidates → `get_endpoint_details` on each.
- "How do I create an order?" → `find_endpoint_by_intent("create order")` → `show_request_example` on `POST /orders`.

Verify these two flows manually against the live Spring Boot app before declaring M2 complete.

## Guardrail summary

| Guardrail | Mechanism |
|---|---|
| No destructive calls by default | `ALLOW_CALL=false` |
| No prod base URLs | `CALL_BASE_URL_ALLOWLIST` |
| No mutating verbs | `ALLOW_MUTATING_CALLS=false` |
| No auth-header leakage | Don't forward process env; explicit `headers` arg only |
| No stack-trace leakage | Catch `httpx` errors; return `{error: "..."}` with a clean message |
| Spec drift tolerated | TTL cache + `stale: true` flag on fetch failure |

## Anti-patterns

- Don't embed an LLM call inside `find_endpoint_by_intent`.
- Don't default `ALLOW_CALL=true` "for convenience."
- Don't return the full OpenAPI spec from a tool — Claude will blow its context.
- Don't skip `$ref` resolution; half-resolved schemas produce confusing LLM outputs.
