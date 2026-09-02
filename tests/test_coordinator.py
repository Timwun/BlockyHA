"""Tests for coordinator partial-data behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.blocky.api import BlockyAuthError, BlockyStatsDisabled
from custom_components.blocky.const import DOMAIN
from custom_components.blocky.coordinator import BlockyDataUpdateCoordinator


def _entry() -> MockConfigEntry:
    """Create a minimal config entry for coordinator tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Blocky",
        data={},
        entry_id="test-entry",
        options={"scan_interval": 30},
    )


@pytest.mark.asyncio
async def test_stats_disabled_keeps_status_available(hass) -> None:
    """Statistics being disabled does not take down the controls."""
    client = type("Client", (), {})()
    client.get_status = AsyncMock(return_value={"enabled": True})
    client.get_stats = AsyncMock(side_effect=BlockyStatsDisabled("disabled", 503))
    coordinator = BlockyDataUpdateCoordinator(hass, _entry(), client, 30)

    data = await coordinator._async_update_data()

    assert data.status["enabled"] is True
    assert data.stats is None


@pytest.mark.asyncio
async def test_status_auth_error_starts_reauth(hass) -> None:
    """Status authentication errors are escalated to Home Assistant."""
    client = type("Client", (), {})()
    client.get_status = AsyncMock(side_effect=BlockyAuthError("bad auth", 401))
    client.get_stats = AsyncMock()
    coordinator = BlockyDataUpdateCoordinator(hass, _entry(), client, 30)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()

    client.get_stats.assert_not_awaited()
