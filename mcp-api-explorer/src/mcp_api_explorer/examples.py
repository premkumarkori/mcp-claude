"""Build a minimal valid request example from a resolved OpenAPI schema.

Rules, in order:
1. Prefer `example` from the schema.
2. Otherwise prefer `default`.
3. Otherwise use the first `enum` value.
4. Otherwise use a type-appropriate placeholder.
Only required fields for objects — keep the example minimal.
"""

from __future__ import annotations

import json
import shlex
from typing import Any

_ISO_INSTANT_PLACEHOLDER = "2026-01-01T00:00:00Z"


def example_for_schema(schema: dict[str, Any] | None) -> Any:
    if not schema or not isinstance(schema, dict):
        return None

    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]

    t = schema.get("type")
    fmt = schema.get("format")

    if t == "object" or "properties" in schema:
        out: dict[str, Any] = {}
        required = set(schema.get("required") or [])
        for name, sub in (schema.get("properties") or {}).items():
            if required and name not in required:
                continue
            out[name] = example_for_schema(sub)
        return out

    if t == "array":
        return [example_for_schema(schema.get("items") or {})]

    if t == "string":
        if fmt in ("date-time", "date"):
            return _ISO_INSTANT_PLACEHOLDER
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        if fmt == "email":
            return "user@example.com"
        return "string"

    if t == "integer":
        return 0
    if t == "number":
        return 0
    if t == "boolean":
        return False

    # Polymorphic / unknown — try oneOf/anyOf/allOf
    for key in ("oneOf", "anyOf", "allOf"):
        if key in schema and schema[key]:
            return example_for_schema(schema[key][0])

    return None


def find_operation(spec: dict[str, Any], path: str, method: str) -> dict[str, Any] | None:
    item = (spec.get("paths") or {}).get(path)
    if not isinstance(item, dict):
        return None
    op = item.get(method.lower())
    return op if isinstance(op, dict) else None


def build_example(
    spec: dict[str, Any], path: str, method: str, base_url: str
) -> dict[str, Any]:
    """Return {"curl", "body", "url"} — the minimal valid request for this endpoint."""
    op = find_operation(spec, path, method)
    if op is None:
        raise ValueError(f"No operation found for {method.upper()} {path}")

    # Build URL with path-param placeholders replaced by examples.
    url_path = path
    query_params: list[tuple[str, Any]] = []
    for p in op.get("parameters") or []:
        if not isinstance(p, dict):
            continue
        name = p.get("name")
        loc = p.get("in")
        schema = p.get("schema") or {}
        required = p.get("required", False) or loc == "path"
        if not name:
            continue
        ex = example_for_schema(schema)
        if loc == "path":
            url_path = url_path.replace("{" + name + "}", str(ex if ex is not None else 1))
        elif loc == "query" and required:
            query_params.append((name, ex))

    url = base_url.rstrip("/") + url_path
    if query_params:
        url += "?" + "&".join(f"{k}={v}" for k, v in query_params)

    body: Any = None
    req_body = op.get("requestBody")
    if isinstance(req_body, dict):
        content = (req_body.get("content") or {}).get("application/json") or {}
        body = example_for_schema(content.get("schema"))

    # Construct a curl string.
    parts = ["curl", "-X", method.upper(), shlex.quote(url)]
    if body is not None:
        parts += ["-H", shlex.quote("Content-Type: application/json")]
        parts += ["-d", shlex.quote(json.dumps(body))]

    return {"url": url, "body": body, "curl": " ".join(parts)}
