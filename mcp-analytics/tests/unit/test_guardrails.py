import pytest
import sqlglot

from mcp_analytics.guardrails import (
    PlanTooExpensive,
    assert_plan_within_budget,
    ensure_limit,
    extract_plan_total_cost,
)


def _parse(sql: str):
    return sqlglot.parse_one(sql, dialect="postgres")


def test_injects_limit_when_missing():
    tree = _parse("SELECT id FROM v_employees_safe")
    capped = ensure_limit(tree, 1000)
    assert "LIMIT 1000" in capped.sql().upper()


def test_lowers_oversized_limit():
    tree = _parse("SELECT id FROM v_employees_safe LIMIT 50000")
    capped = ensure_limit(tree, 1000)
    assert "LIMIT 1000" in capped.sql().upper()


def test_preserves_smaller_limit():
    tree = _parse("SELECT id FROM v_employees_safe LIMIT 10")
    capped = ensure_limit(tree, 1000)
    assert "LIMIT 10" in capped.sql().upper()


def test_rejects_nonpositive_cap():
    tree = _parse("SELECT id FROM v_employees_safe")
    with pytest.raises(ValueError):
        ensure_limit(tree, 0)


def test_extract_plan_total_cost_from_dict_row():
    class FakeRecord(dict):
        pass

    row = FakeRecord({"QUERY PLAN": [{"Plan": {"Total Cost": 42.5}}]})
    assert extract_plan_total_cost([row]) == 42.5


def test_extract_plan_total_cost_from_json_string():
    rows = [{"QUERY PLAN": '[{"Plan": {"Total Cost": 100.0}}]'}]
    assert extract_plan_total_cost(rows) == 100.0


def test_assert_plan_within_budget_rejects_expensive():
    with pytest.raises(PlanTooExpensive):
        assert_plan_within_budget(200_000.0, 100_000.0)


def test_assert_plan_within_budget_accepts_cheap():
    # No exception = pass.
    assert_plan_within_budget(10.0, 100_000.0)
