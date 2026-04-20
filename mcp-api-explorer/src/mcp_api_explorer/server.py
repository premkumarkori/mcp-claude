"""FastMCP wiring for the API Explorer MCP.

Tool parameters are declared as individual typed args (FastMCP-idiomatic) so the
LLM sees flat tool schemas rather than wrapper objects. This is a deliberate
deviation from the `python-mcp-server` skill's "single Pydantic model" advice —
FastMCP's flat-param shape tends to produce better LLM-generated arguments.
Structured inputs with many fields should still use Pydantic.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP

from .caller import CallRefused, call_endpoint
from .config import settings
from .examples import build_example, find_operation
from .intent import find_endpoint_by_intent as _find_by_intent
from .logging import configure as _configure_logging
from .logging import logger
from .spec import SpecCache, iter_operations, summarize_operation

_configure_logging(settings.log_level)

mcp = FastMCP("api-explorer")

_http_client = httpx.AsyncClient(timeout=settings.call_timeout_seconds)
_spec_cache = SpecCache(
    url=settings.api_base_url.rstrip("/") + settings.openapi_path,
    ttl_seconds=settings.spec_cache_ttl_seconds,
)


async def _spec() -> tuple[dict[str, Any], bool]:
    return await _spec_cache.get(_http_client)


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------


@mcp.tool()
async def list_endpoints(tag: str | None = None, method: str | None = None) -> dict[str, Any]:
    """List API endpoints, optionally filtered by tag or HTTP method.

    Returns a compact list — no request/response schemas. Use get_endpoint_details
    for the full view of a single endpoint.
    """
    logger.info("tool.list_endpoints", tag=tag, method=method)
    spec, stale = await _spec()
    method_u = method.upper() if method else None

    items: list[dict[str, Any]] = []
    for p, m, op in iter_operations(spec):
        if method_u and m != method_u:
            continue
        if tag and tag not in (op.get("tags") or []):
            continue
        items.append(summarize_operation(p, m, op))
    items.sort(key=lambda e: (e.get("tag") or "", e["path"], e["method"]))
    return {"stale": stale, "count": len(items), "endpoints": items}


@mcp.tool()
async def get_endpoint_details(path: str, method: str) -> dict[str, Any]:
    """Return the full schema for one endpoint: params, request/response schemas, tags."""
    logger.info("tool.get_endpoint_details", path=path, method=method.upper())
    spec, stale = await _spec()
    op = find_operation(spec, path, method)
    if op is None:
        return {"stale": stale, "error": f"No operation found for {method.upper()} {path}"}
    return {
        "stale": stale,
        "path": path,
        "method": method.upper(),
        "tags": op.get("tags") or [],
        "operationId": op.get("operationId"),
        "summary": op.get("summary"),
        "description": op.get("description"),
        "parameters": op.get("parameters") or [],
        "requestBody": op.get("requestBody"),
        "responses": op.get("responses") or {},
    }


@mcp.tool()
async def find_endpoint_by_intent(query: str, limit: int = 5) -> dict[str, Any]:
    """Rank endpoints by keyword + tag overlap with the query. No LLM inside."""
    logger.info("tool.find_endpoint_by_intent", query=query, limit=limit)
    spec, stale = await _spec()
    results = _find_by_intent(spec, query, limit=max(1, min(limit, 20)))
    return {"stale": stale, "count": len(results), "results": results}


@mcp.tool()
async def show_request_example(path: str, method: str) -> dict[str, Any]:
    """Return a minimal valid example for an endpoint: url, body, curl."""
    logger.info("tool.show_request_example", path=path, method=method.upper())
    spec, stale = await _spec()
    try:
        example = build_example(spec, path, method, settings.api_base_url)
    except ValueError as e:
        return {"stale": stale, "error": str(e)}
    return {"stale": stale, **example}


@mcp.tool()
async def call_endpoint_tool(
    path: str,
    method: str,
    params: dict[str, Any] | None = None,
    body: Any = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Call an endpoint on the target API. DISABLED BY DEFAULT.

    Requires ALLOW_CALL=true (and ALLOW_MUTATING_CALLS=true for non-GET). The
    base URL must be in CALL_BASE_URL_ALLOWLIST. Never forwards process-env
    auth; pass headers explicitly.
    """
    url = settings.api_base_url.rstrip("/") + path
    try:
        return await call_endpoint(
            _http_client, settings, method, url, params=params, body=body, headers=headers
        )
    except CallRefused as e:
        logger.warning("tool.call_endpoint.refused", reason=str(e))
        return {"refused": True, "reason": str(e)}


@mcp.tool()
async def refresh_spec() -> dict[str, Any]:
    """Force a re-fetch of the OpenAPI spec, bypassing the TTL cache."""
    logger.info("tool.refresh_spec")
    spec, stale = await _spec_cache.refresh(_http_client)
    return {"stale": stale, "paths": len(spec.get("paths", {}))}


# --------------------------------------------------------------------------
# Resources — one per endpoint
# --------------------------------------------------------------------------


@mcp.resource("openapi://paths/{encoded_path}/{method}")
async def endpoint_resource(encoded_path: str, method: str) -> str:
    """Full endpoint detail for an `openapi://paths/...` URI."""
    import json
    from urllib.parse import unquote

    path = unquote(encoded_path)
    details = await get_endpoint_details(path, method)
    return json.dumps(details, indent=2, default=str)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main() -> None:
    logger.info(
        "startup",
        api_base_url=settings.api_base_url,
        openapi_path=settings.openapi_path,
        allow_call=settings.allow_call,
        allow_mutating_calls=settings.allow_mutating_calls,
    )
    mcp.run()


if __name__ == "__main__":
    main()


# Small helper used by callers who want to construct a resource URI.
def encode_path_for_resource(path: str) -> str:
    return quote(path, safe="")
