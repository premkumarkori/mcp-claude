from mcp_analytics.config import Settings


def test_table_allowlist_parses_csv_string(monkeypatch):
    monkeypatch.setenv("TABLE_ALLOWLIST", "a, b , c")
    s = Settings(_env_file=None)
    assert s.table_allowlist == ["a", "b", "c"]
    assert s.allowlist_set == {"a", "b", "c"}


def test_table_allowlist_lowercased(monkeypatch):
    monkeypatch.setenv("TABLE_ALLOWLIST", "V_Employees_Safe,V_Orders_Safe")
    s = Settings(_env_file=None)
    assert s.allowlist_set == {"v_employees_safe", "v_orders_safe"}


def test_defaults_are_safe(monkeypatch):
    # Clear env that could influence defaults.
    for k in ("DB_URL", "TABLE_ALLOWLIST", "ROW_CAP"):
        monkeypatch.delenv(k, raising=False)
    s = Settings(_env_file=None)
    assert s.row_cap == 1000
    assert s.inline_row_threshold == 50
    # Default DSN uses the mcp_readonly role — not the app role.
    assert "mcp_readonly" in s.db_url
