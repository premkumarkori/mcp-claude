import pytest

from mcp_analytics.validator import SqlValidationError, validate_select


def test_accepts_simple_select(allowlist):
    tree = validate_select("SELECT * FROM v_employees_safe", allowlist)
    assert tree is not None


def test_accepts_select_with_where_and_limit(allowlist):
    sql = "SELECT id, name FROM v_employees_safe WHERE id > 10 LIMIT 5"
    assert validate_select(sql, allowlist) is not None


def test_accepts_select_with_join_between_allowlisted(allowlist):
    sql = (
        "SELECT o.id FROM v_orders_safe o "
        "JOIN v_employees_safe e ON o.customer_name = e.name"
    )
    assert validate_select(sql, allowlist) is not None


@pytest.mark.parametrize(
    "bad_sql",
    [
        "DROP TABLE employees",
        "TRUNCATE TABLE v_orders_safe",
        "UPDATE v_employees_safe SET name = 'x'",
        "DELETE FROM v_employees_safe",
        "INSERT INTO v_employees_safe(id) VALUES (1)",
        "CREATE TABLE t (id int)",
        "ALTER TABLE v_employees_safe ADD COLUMN x int",
    ],
)
def test_rejects_dml_and_ddl(bad_sql, allowlist):
    with pytest.raises(SqlValidationError):
        validate_select(bad_sql, allowlist)


def test_rejects_non_allowlisted_table(allowlist):
    with pytest.raises(SqlValidationError, match="not in the allowlist"):
        validate_select("SELECT * FROM employees", allowlist)


def test_rejects_mixed_allowlisted_and_raw_table(allowlist):
    sql = (
        "SELECT e.id FROM employees e "
        "JOIN v_orders_safe o ON e.name = o.customer_name"
    )
    with pytest.raises(SqlValidationError, match="not in the allowlist"):
        validate_select(sql, allowlist)


def test_rejects_multiple_statements(allowlist):
    with pytest.raises(SqlValidationError, match="Multiple statements"):
        validate_select(
            "SELECT * FROM v_employees_safe; DROP TABLE employees", allowlist
        )


def test_rejects_empty_sql(allowlist):
    with pytest.raises(SqlValidationError):
        validate_select("", allowlist)
    with pytest.raises(SqlValidationError):
        validate_select("   ", allowlist)


def test_rejects_invalid_sql(allowlist):
    with pytest.raises(SqlValidationError, match="Invalid SQL"):
        validate_select("SELEKT * FROM v_employees_safe", allowlist)


def test_rejects_cte_with_dml(allowlist):
    # CTEs can technically contain INSERT/UPDATE/DELETE in Postgres (data-modifying CTEs).
    sql = (
        "WITH deleted AS (DELETE FROM v_employees_safe RETURNING id) "
        "SELECT * FROM deleted"
    )
    with pytest.raises(SqlValidationError):
        validate_select(sql, allowlist)
