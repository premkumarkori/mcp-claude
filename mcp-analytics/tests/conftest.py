import pytest


@pytest.fixture
def allowlist() -> set[str]:
    return {"v_employees_safe", "v_orders_safe"}
