"""Keyword + tag scoring for `find_endpoint_by_intent`.

This is a *pure function* — no LLM call. The LLM invoking this tool is itself
the reasoning layer; we don't need a second LLM inside the MCP server.
Keep it deterministic, testable, and fast.
"""

from __future__ import annotations

import re
from typing import Any

from .spec import iter_operations, summarize_operation

_STOPWORDS = {
    "a", "an", "the", "of", "for", "to", "in", "on", "with", "and", "or", "by",
    "is", "are", "do", "does", "how", "what", "which", "i", "we", "my", "our",
    "can", "please", "show", "me", "it", "that", "this",
}


def _tokenize(s: str) -> set[str]:
    """Lowercase, split on non-word chars, drop stopwords and single chars."""
    if not s:
        return set()
    tokens = re.split(r"\W+", s.lower())
    return {t for t in tokens if t and len(t) > 1 and t not in _STOPWORDS}


_METHOD_ALIASES = {
    "GET": {"list", "get", "fetch", "read", "show", "retrieve", "find"},
    "POST": {"create", "add", "new", "post", "insert"},
    "PUT": {"update", "put", "replace", "edit", "modify"},
    "PATCH": {"patch", "update", "edit"},
    "DELETE": {"delete", "remove", "destroy"},
}


def score_operation(query_tokens: set[str], op_tokens: set[str], method: str) -> int:
    """Integer score — higher is better. Stable and transparent."""
    if not query_tokens:
        return 0
    base = len(query_tokens & op_tokens) * 10
    # Bonus if the query hints at an HTTP verb aligned with this operation.
    if query_tokens & _METHOD_ALIASES.get(method.upper(), set()):
        base += 5
    return base


def find_endpoint_by_intent(
    spec: dict[str, Any], query: str, limit: int = 5
) -> list[dict[str, Any]]:
    """Return the top-`limit` endpoints ranked by query overlap.

    Each result is `summarize_operation(...) | {"score": int}`. Zero-score
    endpoints are excluded. Ties broken by (path, method) for stability.
    """
    q_tokens = _tokenize(query)
    ranked: list[tuple[int, str, str, dict[str, Any]]] = []
    for path, method, op in iter_operations(spec):
        tags = " ".join(op.get("tags") or [])
        op_text = " ".join(
            filter(
                None,
                [
                    op.get("operationId", ""),
                    op.get("summary", ""),
                    op.get("description", ""),
                    tags,
                    path.replace("/", " ").replace("{", "").replace("}", ""),
                ],
            )
        )
        op_tokens = _tokenize(op_text)
        s = score_operation(q_tokens, op_tokens, method)
        if s > 0:
            ranked.append((s, path, method, op))

    ranked.sort(key=lambda r: (-r[0], r[1], r[2]))
    results: list[dict[str, Any]] = []
    for score, path, method, op in ranked[:limit]:
        summary = summarize_operation(path, method, op)
        summary["score"] = score
        results.append(summary)
    return results
