"""Tests for the Blocky HTTP client."""

from __future__ import annotations

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.blocky.api import (
    BlockyApiError,
    BlockyClient,
    BlockyStatsDisabled,
    is_valid_duration,
)
from custom_components.blocky.const import (
    CONF_BASE_URL,
    CONF_DISABLE_PATH,
    CONF_ENABLE_PATH,
    CONF_LISTS_REFRESH_PATH,
    CONF_STATS_PATH,
    CONF_STATUS_PATH,
)

pytestmark = pytest.mark.enable_socket

BASE_CONFIG = {
    CONF_BASE_URL: "http://blocky.local",
    CONF_STATUS_PATH: "/api/blocking/status",
    CONF_ENABLE_PATH: "/api/blocking/enable",
    CONF_DISABLE_PATH: "/api/blocking/disable",
    CONF_LISTS_REFRESH_PATH: "/api/lists/refresh",
    CONF_STATS_PATH: "/api/stats",
}


@pytest.mark.asyncio
async def test_get_status_and_stats(api_server) -> None:
    """Status and stats are decoded from the configured endpoints."""
    base_url, _state = api_server
    config = {**BASE_CONFIG, CONF_BASE_URL: base_url}
    async with aiohttp.ClientSession() as session:
        client = BlockyClient(session, config)
        assert (await client.get_status())["enabled"] is True
        assert (await client.get_stats())["summary"]["queries"] == 42


@pytest.mark.asyncio
async def test_base_path_is_preserved(api_server) -> None:
    """A reverse-proxy prefix is not discarded when joining paths."""
    base_url, state = api_server
    config = {**BASE_CONFIG, CONF_BASE_URL: f"{base_url}/blocky"}
    state["enabled"] = False
    async with aiohttp.ClientSession() as session:
        client = BlockyClient(session, config)
        assert (await client.get_status())["enabled"] is False
    assert state["last_path"].endswith("/blocky/api/blocking/status")


@pytest.mark.asyncio
async def test_basic_auth_is_sent(api_server) -> None:
    """Configured proxy credentials are attached to API requests."""
    base_url, state = api_server
    config = {
        **BASE_CONFIG,
        CONF_BASE_URL: base_url,
        "username": "user",
        "password": "secret",
    }
    async with aiohttp.ClientSession() as session:
        client = BlockyClient(session, config)
        await client.get_status()
    assert state["last_auth"].startswith("Basic ")


@pytest.mark.asyncio
async def test_disable_omits_empty_query_parameters(api_server) -> None:
    """An indefinite disable request has no invalid empty query values."""
    base_url, state = api_server
    config = {**BASE_CONFIG, CONF_BASE_URL: base_url}
    async with aiohttp.ClientSession() as session:
        client = BlockyClient(session, config)
        await client.disable_blocking()
    assert state["last_query"] == {}


@pytest.mark.asyncio
async def test_disable_sends_supplied_parameters(api_server) -> None:
    """Duration and groups are passed only when supplied."""
    base_url, state = api_server
    config = {**BASE_CONFIG, CONF_BASE_URL: base_url}
    async with aiohttp.ClientSession() as session:
        client = BlockyClient(session, config)
        await client.disable_blocking("30m", "ads,tracker")
    assert state["last_query"] == {"duration": "30m", "groups": "ads,tracker"}


@pytest.mark.asyncio
async def test_stats_disabled_is_distinguishable(api_server) -> None:
    """Blocky's expected disabled-statistics response has its own exception."""
    base_url, state = api_server
    config = {**BASE_CONFIG, CONF_BASE_URL: base_url}
    state["stats_status"] = 503
    async with aiohttp.ClientSession() as session:
        client = BlockyClient(session, config)
        with pytest.raises(BlockyStatsDisabled):
            await client.get_stats()


@pytest.mark.asyncio
async def test_http_errors_are_exposed(api_server) -> None:
    """Unexpected HTTP responses remain actionable to callers."""
    base_url, state = api_server
    config = {**BASE_CONFIG, CONF_BASE_URL: base_url}
    state["refresh_status"] = 500
    async with aiohttp.ClientSession() as session:
        client = BlockyClient(session, config)
        with pytest.raises(BlockyApiError, match="failed"):
            await client.refresh_lists()


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("5m", True),
        ("1h30m", True),
        ("0.5s", True),
        ("5m30s", True),
        ("", False),
        ("30", False),
        ("-5m", False),
        ("5d", False),
    ),
)
def test_duration_validation(value: str, expected: bool) -> None:
    """The service accepts Blocky's supported duration units."""
    assert is_valid_duration(value) is expected


@pytest_asyncio.fixture
async def api_server():
    """Run a local server that models the Blocky endpoint responses."""
    state = {
        "enabled": True,
        "stats_status": 200,
        "refresh_status": 200,
        "last_path": "",
        "last_query": {},
        "last_auth": "",
    }

    async def handler(request: web.Request) -> web.StreamResponse:
        state["last_path"] = request.path
        state["last_query"] = dict(request.query)
        state["last_auth"] = request.headers.get("Authorization", "")
        if request.path.endswith("/blocking/status"):
            return web.json_response({"enabled": state["enabled"]})
        if request.path.endswith("/stats"):
            if state["stats_status"] != 200:
                return web.Response(status=state["stats_status"], text="statistics are disabled")
            return web.json_response({"summary": {"queries": 42}})
        if request.path.endswith("/lists/refresh"):
            return web.Response(status=state["refresh_status"], text="failed")
        return web.Response(status=200)

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    server = TestServer(app)
    await server.start_server()
    try:
        yield str(server.make_url("/")).rstrip("/"), state
    finally:
        await server.close()
