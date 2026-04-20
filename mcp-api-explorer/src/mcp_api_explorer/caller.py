"""Gated `call_endpoint` implementation.

Every check is explicit and independently testable. See PRD §7.
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import Settings
from .logging import logger

_SAFE_METHODS = {"GET"}
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_BODY_PREVIEW_BYTES = 2048


class CallRefused(Exception):
    """Raised when a call is refused by a guardrail. Message is LLM-readable."""


def _assert_allowed(method: str, url: str, settings: Settings) -> None:
    method_u = method.upper()

    if not settings.allow_call:
        raise CallRefused(
            "call_endpoint is disabled. Set ALLOW_CALL=true to enable (PRD §7)."
        )

    if method_u not in _SAFE_METHODS and method_u not in _MUTATING_METHODS:
        raise CallRefused(f"Unsupported HTTP method: {method_u!r}")

    if method_u in _MUTATING_METHODS and not settings.allow_mutating_calls:
        raise CallRefused(
            f"Mutating method {method_u} is disabled. "
            "Set ALLOW_MUTATING_CALLS=true (and ALLOW_CALL=true) to enable."
        )

    allowed = [b.rstrip("/") for b in settings.call_base_url_allowlist]
    if not any(url.startswith(b + "/") or url == b for b in allowed):
        raise CallRefused(
            f"Base URL not in CALL_BASE_URL_ALLOWLIST. Allowed: {allowed}"
        )


async def call_endpoint(
    client: httpx.AsyncClient,
    settings: Settings,
    method: str,
    url: str,
    params: dict[str, Any] | None = None,
    body: Any = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Make an outbound HTTP call if (and only if) guardrails permit it.

    Returns a summary: {status, headers, body_preview, body_truncated}.
    Never forwards process environment auth — only the explicit `headers` arg.
    """
    _assert_allowed(method, url, settings)

    logger.info(
        "call_endpoint.allowed",
        method=method.upper(),
        url=url,
        has_body=body is not None,
    )

    try:
        r = await client.request(
            method.upper(),
            url,
            params=params,
            json=body if body is not None else None,
            headers=headers or {},
            timeout=settings.call_timeout_seconds,
        )
    except httpx.HTTPError as e:
        logger.warning("call_endpoint.http_error", error=str(e))
        return {"error": f"HTTP error: {type(e).__name__}: {e}"}

    raw = r.content or b""
    preview = raw[:_BODY_PREVIEW_BYTES]
    try:
        body_preview: Any = preview.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        body_preview = f"<{len(preview)} bytes, non-utf8>"

    return {
        "status": r.status_code,
        "headers": dict(r.headers),
        "body_preview": body_preview,
        "body_truncated": len(raw) > _BODY_PREVIEW_BYTES,
        "body_size_bytes": len(raw),
    }
