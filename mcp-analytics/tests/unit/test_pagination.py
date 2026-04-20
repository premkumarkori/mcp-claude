from decimal import Decimal

from mcp_analytics.pagination import build_result, row_to_dict, summarize


def test_row_to_dict_coerces_decimal_and_datetime():
    from datetime import datetime

    class FakeRecord(dict):
        pass

    rec = FakeRecord({"amount": Decimal("12.50"), "created_at": datetime(2026, 4, 20, 10, 0)})
    out = row_to_dict(rec)
    assert out["amount"] == 12.5
    assert out["created_at"].startswith("2026-04-20")


def test_summarize_numeric_and_string_columns():
    rows = [
        {"amount": 10, "status": "PENDING"},
        {"amount": 20, "status": "PENDING"},
        {"amount": 30, "status": "SHIPPED"},
    ]
    s = summarize(["amount", "status"], rows)
    assert s["columns"]["amount"]["min"] == 10
    assert s["columns"]["amount"]["max"] == 30
    assert s["columns"]["amount"]["non_null"] == 3
    assert s["columns"]["status"]["distinct"] == 2
    # top-K reports ("PENDING", 2) before ("SHIPPED", 1)
    top = s["columns"]["status"]["top"]
    assert top[0] == ("PENDING", 2)


def test_summarize_counts_nulls():
    rows = [{"x": None}, {"x": 1}, {"x": None}]
    s = summarize(["x"], rows)
    assert s["columns"]["x"]["null"] == 2
    assert s["columns"]["x"]["non_null"] == 1


def test_build_result_inline_path_when_small():
    rows = [{"id": i} for i in range(10)]
    r = build_result(["id"], rows, truncated=False, inline_threshold=50, export_id=None)
    assert r.rows == rows
    assert r.summary is None
    assert r.export_id is None
    assert r.row_count == 10


def test_build_result_summary_path_when_large():
    rows = [{"id": i} for i in range(100)]
    r = build_result(
        ["id"], rows, truncated=False, inline_threshold=50, export_id="abc"
    )
    assert r.rows == []
    assert r.summary is not None
    assert r.export_id == "abc"
    assert r.row_count == 100
