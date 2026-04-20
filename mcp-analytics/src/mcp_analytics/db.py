"""asyncpg connection pool (Layer 2).

Every acquired connection is forced into a read-only transaction with a short
statement timeout — redundant with the `mcp_readonly` role defaults but kept
as belt-and-suspenders.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from .logging import logger


class DB:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self, min_size: int = 1, max_size: int = 5) -> None:
        if self.pool is not None:
            return
        self.pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=min_size,
            max_size=max_size,
            server_settings={
                "default_transaction_read_only": "on",
                "statement_timeout": "5000",
                "idle_in_transaction_session_timeout": "10000",
            },
        )
        logger.info("db.pool.ready")

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def fetch(self, sql: str, *args: Any, timeout: float = 6.0) -> list[asyncpg.Record]:
        assert self.pool is not None, "DB.connect() not called"
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql, *args, timeout=timeout)

    async def fetch_explain(self, sql: str, *args: Any, timeout: float = 3.0) -> list[Any]:
        assert self.pool is not None, "DB.connect() not called"
        async with self.pool.acquire() as conn:
            return await conn.fetch(f"EXPLAIN (FORMAT JSON) {sql}", *args, timeout=timeout)
