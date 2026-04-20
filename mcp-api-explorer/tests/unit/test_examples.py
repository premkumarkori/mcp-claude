from mcp_api_explorer.examples import build_example, example_for_schema


def test_example_for_primitive_types():
    assert example_for_schema({"type": "string"}) == "string"
    assert example_for_schema({"type": "integer"}) == 0
    assert example_for_schema({"type": "boolean"}) is False


def test_example_prefers_schema_example():
    assert example_for_schema({"type": "string", "example": "hello"}) == "hello"


def test_example_uses_enum_when_no_example_or_default():
    s = {"type": "string", "enum": ["A", "B"]}
    assert example_for_schema(s) == "A"


def test_object_example_only_includes_required_fields():
    s = {
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string"},
            "optional_extra": {"type": "integer"},
        },
    }
    out = example_for_schema(s)
    assert "name" in out
    assert "optional_extra" not in out


def test_build_example_post_orders_has_body_and_curl(openapi_spec):
    result = build_example(openapi_spec, "/orders", "POST", "http://localhost:8080")
    assert result["url"] == "http://localhost:8080/orders"
    body = result["body"]
    assert set(body.keys()) == {"customerName", "amount"}  # required-only
    curl = result["curl"]
    assert curl.startswith("curl -X POST")
    assert "Content-Type: application/json" in curl


def test_build_example_get_with_path_param(openapi_spec):
    result = build_example(openapi_spec, "/employees/{id}", "GET", "http://localhost:8080")
    # Path param placeholder must be substituted.
    assert "{id}" not in result["url"]
    assert result["body"] is None
    assert result["curl"].startswith("curl -X GET")


def test_build_example_raises_on_unknown_endpoint(openapi_spec):
    import pytest

    with pytest.raises(ValueError):
        build_example(openapi_spec, "/nope", "GET", "http://localhost:8080")
