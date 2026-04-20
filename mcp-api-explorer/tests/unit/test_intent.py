from mcp_api_explorer.intent import find_endpoint_by_intent


def test_create_order_ranks_post_orders_first(openapi_spec):
    results = find_endpoint_by_intent(openapi_spec, "create order")
    assert results, "expected at least one result"
    top = results[0]
    assert top["path"] == "/orders"
    assert top["method"] == "POST"


def test_list_employees_prefers_get(openapi_spec):
    results = find_endpoint_by_intent(openapi_spec, "list employees")
    assert results[0]["path"] == "/employees"
    assert results[0]["method"] == "GET"


def test_delete_employee_matches_delete_verb(openapi_spec):
    results = find_endpoint_by_intent(openapi_spec, "delete an employee")
    # DELETE /employees/{id} must appear in top results.
    paths_methods = [(r["path"], r["method"]) for r in results]
    assert ("/employees/{id}", "DELETE") in paths_methods


def test_empty_query_returns_empty_list(openapi_spec):
    assert find_endpoint_by_intent(openapi_spec, "") == []


def test_limit_respected(openapi_spec):
    results = find_endpoint_by_intent(openapi_spec, "employees orders", limit=2)
    assert len(results) <= 2
