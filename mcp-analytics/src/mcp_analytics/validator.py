"""SQL parser-layer validation (Layer 3 of the 4-layer pipeline).

Rejects anything that is not a single, allowlisted SELECT before the query
ever reaches the database. This is belt-and-suspenders: Layer 1 (the DB role)
is the authoritative safety net, but defense in depth matters when the parser
catches bugs in earlier layers.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp


class SqlValidationError(ValueError):
    """Raised when SQL fails a parser-layer check. Message is safe to return to the LLM."""


_FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,  # DDL-ish commands sqlglot can't classify (VACUUM, etc.)
)


def validate_select(sql: str, allowlist: set[str]) -> sqlglot.Expression:
    """Return a parsed tree if the SQL is a single, allowlisted SELECT; otherwise raise."""
    if not sql or not sql.strip():
        raise SqlValidationError("Empty SQL.")

    try:
        statements = sqlglot.parse(sql, dialect="postgres")
    except sqlglot.errors.ParseError as e:
        raise SqlValidationError(f"Invalid SQL: {e}") from e

    if not statements:
        raise SqlValidationError("Empty SQL.")

    if len(statements) > 1:
        raise SqlValidationError("Multiple statements not allowed; provide a single SELECT.")

    tree = statements[0]
    if tree is None:
        raise SqlValidationError("Empty SQL.")

    # Top-level must be a SELECT (or a Subqueryable wrapper containing one, e.g. parenthesized).
    if not isinstance(tree, (exp.Select, exp.Subquery, exp.Union)):
        raise SqlValidationError(
            f"Only SELECT queries are allowed (got {type(tree).__name__})."
        )

    # No DML / DDL anywhere — including inside subqueries or CTEs.
    for forbidden in _FORBIDDEN_NODES:
        node = tree.find(forbidden)
        if node is not None:
            raise SqlValidationError(
                f"{forbidden.__name__} is not allowed (found in query)."
            )

    # Allowlist check — every table/view reference must be in the allowlist.
    allowlist_lower = {t.lower() for t in allowlist}
    for tbl in tree.find_all(exp.Table):
        name = (tbl.name or "").lower()
        if not name:
            continue
        if name not in allowlist_lower:
            raise SqlValidationError(
                f"Table or view {tbl.name!r} is not in the allowlist."
            )

    return tree
