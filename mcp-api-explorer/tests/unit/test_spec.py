import httpx
import pytest
import respx

from mcp_api_explorer.spec import SpecCache, iter_operations, summarize_operation


def test_iter_operations_covers_all(openapi_spec):
    ops = list(iter_operations(openapi_spec))
    # employees: GET, POST, GET/{id}, DELETE/{id} = 4; orders: GET, POST = 2.
    assert len(ops) == 6
    methods = {(p, m) for p, m, _ in ops}
    assert ("/employees", "GET") in methods
    assert ("/orders", "POST") in methods


def test_summarize_operation_shape(openapi_spec):
    paths = openapi_spec["paths"]
    s = summarize_operation("/orders", "POST", paths["/orders"]["post"])
    assert s["path"] == "/orders"
    assert s["method"] == "POST"
    assert s["tag"] == "Orders"
    assert s["operationId"] == "createOrder"
    assert "Create" in s["summary"]


@pytest.mark.asyncio
@respx.mock
async def test_spec_cache_fetch_and_ttl(openapi_spec):
    url = "http://fake.local/v3/api-docs"
    route = respx.get(url).mock(return_value=httpx.Response(200, json=openapi_spec))

    cache = SpecCache(url=url, ttl_seconds=60)
    async with httpx.AsyncClient() as client:
        spec1, stale1 = await cache.get(client)
        spec2, stale2 = await cache.get(client)  # should hit cache
    assert stale1 is False and stale2 is False
    assert spec1 is spec2 or spec1 == spec2
    assert route.call_count == 1  # cache kept us from a second call


@pytest.mark.asyncio
@respx.mock
async def test_spec_cache_stale_on_error(openapi_spec):
    url = "http://fake.local/v3/api-docs"
    # First call succeeds, second fails.
    respx.get(url).mock(
        side_effect=[
            httpx.Response(200, json=openapi_spec),
            httpx.Response(500, text="boom"),
        ]
    )
    cache = SpecCache(url=url, ttl_seconds=0)  # force refresh every call
    async with httpx.AsyncClient() as client:
        _, stale1 = await cache.get(client)
        spec2, stale2 = await cache.get(client)
    assert stale1 is False
    assert stale2 is True
    assert "paths" in spec2  # served from cache
