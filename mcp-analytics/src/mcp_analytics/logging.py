"""Structured JSON logging to stderr.

Stdout belongs to the MCP stdio protocol. Never log raw rows, never log secrets.
"""

from __future__ import annotations

import logging
import sys

import structlog

_REDACT_KEYS = {
    "password",
    "token",
    "secret",
    "api_key",
    "authorization",
    "cookie",
    "dsn",
    "db_url",
}


def _redact(_logger, _method, event_dict):
    for k in list(event_dict.keys()):
        if k.lower() in _REDACT_KEYS:
            event_dict[k] = "[REDACTED]"
    return event_dict


def configure(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        stream=sys.stderr,
        format="%(message)s",
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger("mcp_analytics")
