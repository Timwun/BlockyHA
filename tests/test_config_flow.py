"""Tests for the Blocky config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.blocky.const import CONF_BASE_URL, CONF_SCAN_INTERVAL, DOMAIN


@pytest.mark.asyncio
async def test_user_flow_validates_and_creates_entry(hass, enable_custom_integrations) -> None:
    """A valid base URL proceeds through settings and creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_BASE_URL: "http://blocky.local/"}
    )
    assert result["step_id"] == "settings"

    with patch(
        "custom_components.blocky.config_flow._async_validate_connection",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_SCAN_INTERVAL: 60}
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_BASE_URL] == "http://blocky.local"
    assert result["data"][CONF_SCAN_INTERVAL] == 60


@pytest.mark.asyncio
async def test_user_flow_rejects_invalid_url(hass, enable_custom_integrations) -> None:
    """The first step reports malformed URLs without making a request."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_BASE_URL: "blocky.local"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_BASE_URL: "invalid_url"}


@pytest.mark.asyncio
async def test_reconfigure_updates_existing_entry(hass, enable_custom_integrations) -> None:
    """Reconfigure updates the existing entry rather than creating another one."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Blocky",
        data={CONF_BASE_URL: "http://old-blocky.local"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["step_id"] == "reconfigure"

    with patch(
        "custom_components.blocky.config_flow._async_validate_connection",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_BASE_URL: "http://new-blocky.local", CONF_SCAN_INTERVAL: 45},
        )

    assert result["type"] == "abort"
    assert hass.config_entries.async_get_entry(entry.entry_id).data[CONF_BASE_URL] == (
        "http://new-blocky.local"
    )
