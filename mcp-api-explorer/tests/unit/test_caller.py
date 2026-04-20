import httpx
import pytest
import respx

from mcp_api_explorer.caller import CallRefused, call_endpoint
from mcp_api_explorer.config import Settings


def _settings(**overrides) -> Settings:
    defaults = dict(
        api_base_url="http://localhost:8080",
        openapi_path="/v3/api-docs",
        spec_cache_ttl_seconds=60,
        allow_call=False,
        allow_mutating_calls=False,
        call_base_url_allowlist=["http://localhost:8080"],
        call_timeout_seconds=5.0,
        log_level="WARNING",
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.asyncio
async def test_refused_by_default():
    async with httpx.AsyncClient() as client:
        with pytest.raises(CallRefused, match="ALLOW_CALL=true"):
            await call_endpoint(
                client, _settings(), "GET", "http://localhost:8080/health"
            )


@pytest.mark.asyncio
async def test_refused_for_url_outside_allowlist():
    async with httpx.AsyncClient() as client:
        with pytest.raises(CallRefused, match="CALL_BASE_URL_ALLOWLIST"):
            await call_endpoint(
                client,
                _settings(allow_call=True),
                "GET",
                "https://api.prod.example.com/v1/x",
            )


@pytest.mark.asyncio
async def test_refused_for_mutating_without_flag():
    async with httpx.AsyncClient() as client:
        with pytest.raises(CallRefused, match="Mutating method POST"):
            await call_endpoint(
                client,
                _settings(allow_call=True),
                "POST",
                "http://localhost:8080/orders",
                body={"a": 1},
            )


@pytest.mark.asyncio
@respx.mock
async def test_allowed_get_returns_preview():
    respx.get("http://localhost:8080/health").mock(
        return_value=httpx.Response(200, json={"status": "UP"})
    )
    async with httpx.AsyncClient() as client:
        result = await call_endpoint(
            client, _settings(allow_call=True), "GET", "http://localhost:8080/health"
        )
    assert result["status"] == 200
    assert "UP" in result["body_preview"]
    assert result["body_truncated"] is False


@pytest.mark.asyncio
@respx.mock
async def test_allowed_post_when_mutating_enabled():
    respx.post("http://localhost:8080/orders").mock(
        return_value=httpx.Response(201, json={"id": 1})
    )
    async with httpx.AsyncClient() as client:
        result = await call_endpoint(
            client,
            _settings(allow_call=True, allow_mutating_calls=True),
            "POST",
            "http://localhost:8080/orders",
            body={"customerName": "X", "amount": 10},
        )
    assert result["status"] == 201
