"""Execution-layer guardrails (Layer 4).

- Force a LIMIT clause, capped at ROW_CAP.
- Run EXPLAIN (FORMAT JSON); reject plans with Total Cost > MAX_PLAN_COST.
"""

from __future__ import annotations

from typing import Any

import sqlglot
from sqlglot import exp


class PlanTooExpensive(ValueError):
    """Raised when the query plan's total cost exceeds the configured cap."""


def ensure_limit(tree: sqlglot.Expression, max_rows: int) -> sqlglot.Expression:
    """Return a tree with a LIMIT clause capped at `max_rows`.

    If the query already has a smaller LIMIT, leave it alone. If larger or missing,
    force it down to `max_rows`. Returns a NEW tree; does not mutate the input.
    """
    if max_rows <= 0:
        raise ValueError("max_rows must be positive.")

    existing = tree.args.get("limit") if hasattr(tree, "args") else None
    if existing is not None:
        # Try to read the literal. If it's an expression we can't introspect, force cap.
        expr = existing.expression if hasattr(existing, "expression") else None
        if isinstance(expr, exp.Literal) and expr.is_int:
            try:
                n = int(expr.this)
                if n <= max_rows:
                    return tree.copy()
            except (ValueError, TypeError):
                pass

    if hasattr(tree, "limit"):
        return tree.limit(max_rows, copy=True)
    # Fall back to wrapping as a string — should never happen for Select/Union.
    return sqlglot.parse_one(f"SELECT * FROM ({tree.sql()}) _t LIMIT {max_rows}", dialect="postgres")


def extract_plan_total_cost(explain_rows: list[Any]) -> float:
    """Given the rows returned by `EXPLAIN (FORMAT JSON) ...`, return the plan total cost.

    Postgres returns a single row with one column, a JSON array of length 1:
        [{"Plan": {"Total Cost": 12.34, ...}, ...}]
    Normalize across asyncpg (which returns a list[dict]) and plain dicts.
    """
    if not explain_rows:
        raise ValueError("EXPLAIN returned no rows.")

    first = explain_rows[0]
    # asyncpg Record -> dict-like
    if hasattr(first, "keys"):
        # Single column named "QUERY PLAN"
        col_val = None
        for key in first.keys():
            col_val = first[key]
            break
    else:
        col_val = first

    # col_val is usually a JSON-ish list already (asyncpg decodes JSON columns to Python)
    if isinstance(col_val, str):
        import json

        col_val = json.loads(col_val)

    if isinstance(col_val, list) and col_val:
        plan_wrapper = col_val[0]
        plan = plan_wrapper.get("Plan") if isinstance(plan_wrapper, dict) else None
        if isinstance(plan, dict) and "Total Cost" in plan:
            return float(plan["Total Cost"])

    raise ValueError("Could not read Total Cost from EXPLAIN output.")


def assert_plan_within_budget(total_cost: float, max_cost: float) -> None:
    if total_cost > max_cost:
        raise PlanTooExpensive(
            f"Query plan total cost {total_cost:.0f} exceeds MAX_PLAN_COST {max_cost:.0f}."
        )
