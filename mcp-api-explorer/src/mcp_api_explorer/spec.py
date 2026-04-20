"""OpenAPI spec fetch + TTL cache + $ref resolution.

On fetch failure: serve the last successful cached version and surface a
`stale: True` flag. Don't hard-fail the MCP server — the LLM can still
answer questions from the cached spec.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import jsonref

from .logging import logger


class SpecCache:
    """Caches the OpenAPI JSON with a TTL and `$ref` resolution done once."""

    def __init__(self, url: str, ttl_seconds: int) -> None:
        self.url = url
        self.ttl_seconds = ttl_seconds
        self._spec: dict[str, Any] | None = None
        self._fetched_at: float = 0.0
        self._stale: bool = False
        self._lock = asyncio.Lock()

    def _is_fresh(self) -> bool:
        return self._spec is not None and (time.monotonic() - self._fetched_at) < self.ttl_seconds

    async def get(self, client: httpx.AsyncClient) -> tuple[dict[str, Any], bool]:
        """Return (spec, stale). Fetches if expired; falls back to cache on error."""
        if self._is_fresh():
            assert self._spec is not None
            return self._spec, self._stale

        async with self._lock:
            if self._is_fresh():
                assert self._spec is not None
                return self._spec, self._stale
            return await self._fetch(client)

    async def refresh(self, client: httpx.AsyncClient) -> tuple[dict[str, Any], bool]:
        """Force a fetch, bypassing TTL."""
        async with self._lock:
            return await self._fetch(client)

    async def _fetch(self, client: httpx.AsyncClient) -> tuple[dict[str, Any], bool]:
        try:
            r = await client.get(self.url, timeout=10.0)
            r.raise_for_status()
            raw = r.json()
            # Resolve $ref references once so downstream code sees concrete schemas.
            resolved = jsonref.replace_refs(raw, proxies=False, lazy_load=False)
            # jsonref returns a lazy proxy-like structure; normalize to plain dict via
            # a round-trip through json.dumps/loads to strip the proxy wrapper.
            import json

            self._spec = json.loads(json.dumps(resolved))
            self._fetched_at = time.monotonic()
            self._stale = False
            logger.info("spec.fetch.ok", url=self.url, paths=len(self._spec.get("paths", {})))
            return self._spec, False
        except Exception as e:  # noqa: BLE001 — we deliberately catch all here
            if self._spec is not None:
                self._stale = True
                logger.warning("spec.fetch.stale", url=self.url, error=str(e))
                return self._spec, True
            logger.error("spec.fetch.fail", url=self.url, error=str(e))
            raise


def iter_operations(spec: dict[str, Any]):
    """Yield (path, method, operation_dict) for every operation in a resolved spec."""
    methods = {"get", "post", "put", "patch", "delete", "head", "options"}
    for path, item in spec.get("paths", {}).items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() in methods and isinstance(op, dict):
                yield path, method.upper(), op


def summarize_operation(path: str, method: str, op: dict[str, Any]) -> dict[str, Any]:
    """Compact shape returned by list_endpoints."""
    tags = op.get("tags") or []
    return {
        "path": path,
        "method": method,
        "tag": tags[0] if tags else None,
        "operationId": op.get("operationId"),
        "summary": op.get("summary"),
    }
