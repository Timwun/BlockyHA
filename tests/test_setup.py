"""End-to-end config-entry setup tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.blocky.const import (
    CONF_BASE_URL,
    CONF_DISABLE_PATH,
    CONF_ENABLE_PATH,
    CONF_LISTS_REFRESH_PATH,
    CONF_STATS_PATH,
    CONF_STATUS_PATH,
    DOMAIN,
)

CONFIG = {
    CONF_BASE_URL: "http://blocky.local",
    CONF_USERNAME: "",
    CONF_PASSWORD: "",
    CONF_STATUS_PATH: "/api/blocking/status",
    CONF_ENABLE_PATH: "/api/blocking/enable",
    CONF_DISABLE_PATH: "/api/blocking/disable",
    CONF_LISTS_REFRESH_PATH: "/api/lists/refresh",
    CONF_STATS_PATH: "/api/stats",
}


@pytest.mark.asyncio
async def test_setup_creates_entities_and_unloads(hass, enable_custom_integrations) -> None:
    """A config entry forwards all platforms and can be unloaded."""
    entry = MockConfigEntry(domain=DOMAIN, title="Blocky", data=CONFIG)
    entry.add_to_hass(hass)

    fake_client = type("Client", (), {})()
    fake_client.base_url = CONFIG[CONF_BASE_URL]
    fake_client.get_status = AsyncMock(return_value={"enabled": True})
    fake_client.get_stats = AsyncMock(
        return_value={
            "byQueryType": {"A": 7, "AAAA": 3},
            "lists": {
                "denylist": {"ads": 100, "tracker": 25},
                "allowlist": {"ads": 4},
            },
            "summary": {
                "queries": 10,
                "blocked": 2,
                "cached": 3,
                "forwarded": 4,
                "local": 1,
                "filtered": 0,
                "errors": 0,
                "dropped": 0,
                "avgResponseMs": 12,
                "cacheHitRate": 0.3,
            },
            "cache": {"entries": 5},
        }
    )

    with patch("custom_components.blocky.BlockyClient", return_value=fake_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == 16
    assert hass.states.get("switch.blocky_blocking").state == "on"
    assert hass.states.get("sensor.blocky_queries_24h").state == "10"
    assert hass.states.get("sensor.blocky_cache_hit_rate").state == "30.0"
    assert hass.states.get("sensor.blocky_denylist_entries").state == "125"
    assert hass.states.get("sensor.blocky_denylist_entries").attributes["groups"] == {
        "ads": 100,
        "tracker": 25,
    }
    assert hass.states.get("sensor.blocky_allowlist_entries").state == "4"
    assert hass.states.get("sensor.blocky_query_types").state == "2"
    assert hass.states.get("sensor.blocky_query_types").attributes["query_types"] == {
        "A": 7,
        "AAAA": 3,
    }

    fake_client.disable_blocking = AsyncMock()
    await hass.services.async_call(
        DOMAIN,
        "disable_for_duration",
        {
            "config_entry_id": entry.entry_id,
            "duration": "30m",
            "groups": "ads,tracker",
        },
        blocking=True,
    )
    fake_client.disable_blocking.assert_awaited_once_with("30m", "ads,tracker")

    assert await hass.config_entries.async_unload(entry.entry_id)
