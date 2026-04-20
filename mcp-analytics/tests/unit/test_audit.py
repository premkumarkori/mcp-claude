import json
from pathlib import Path

from mcp_analytics.audit import AuditLog


def test_audit_appends_jsonl_entry(tmp_path: Path):
    log = AuditLog(tmp_path / "audit" / "queries.jsonl")
    log.record(tool="run_query", sql="SELECT 1", row_count=0, duration_ms=1.5)
    log.record(tool="list_tables")

    lines = (tmp_path / "audit" / "queries.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["tool"] == "run_query"
    assert first["sql"] == "SELECT 1"
    assert "ts" in first
    assert first["row_count"] == 0

    second = json.loads(lines[1])
    assert second["tool"] == "list_tables"
    # None fields are dropped.
    assert "sql" not in second
    assert "row_count" not in second


def test_audit_does_not_leak_rows(tmp_path: Path):
    """The audit log must NEVER record raw result rows."""
    log = AuditLog(tmp_path / "audit.jsonl")
    # Simulate a typical callsite: only counts, no row contents.
    log.record(
        tool="run_query",
        sql="SELECT name FROM v_employees_safe LIMIT 10",
        row_count=10,
        truncated=False,
        duration_ms=12.0,
    )
    content = (tmp_path / "audit.jsonl").read_text()
    # No PII-looking values should be present.
    assert "@example.com" not in content
    assert '"rows"' not in content


def test_audit_creates_parent_dir(tmp_path: Path):
    nested = tmp_path / "a" / "b" / "c" / "audit.jsonl"
    log = AuditLog(nested)
    log.record(tool="x")
    assert nested.exists()
