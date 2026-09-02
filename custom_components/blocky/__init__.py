"""The Blocky Home Assistant integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo

from .api import (
    BlockyApiError,
    BlockyClient,
    is_valid_duration,
    raise_action_error,
)
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DURATION,
    ATTR_GROUPS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_DISABLE_FOR_DURATION,
)
from .coordinator import BlockyDataUpdateCoordinator, BlockyRuntimeData

type BlockyConfigEntry = ConfigEntry[BlockyRuntimeData]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_DURATION): cv.string,
        vol.Optional(ATTR_GROUPS): cv.string,
    }
)


def _entry_config(entry: ConfigEntry) -> dict[str, Any]:
    """Return connection data with options overriding optional settings."""
    config = dict(entry.data)
    config.update(entry.options)
    return config


async def async_setup(hass: HomeAssistant, config: Mapping[str, Any]) -> bool:
    """Register integration-wide service actions."""

    async def handle_disable_for_duration(call: ServiceCall) -> None:
        """Disable blocking for the requested duration."""
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError("Blocky config entry was not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Blocky config entry is not loaded")

        duration = call.data[ATTR_DURATION].strip()
        if not duration or not is_valid_duration(duration):
            raise ServiceValidationError(
                "duration must use Blocky's duration format, for example 30m"
            )
        groups = call.data.get(ATTR_GROUPS, "").strip() or None
        runtime = entry.runtime_data
        try:
            await runtime.client.disable_blocking(duration, groups)
        except BlockyApiError as err:
            await raise_action_error(hass, entry, err, "duration action")
        await runtime.coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE_FOR_DURATION,
        handle_disable_for_duration,
        schema=SERVICE_SCHEMA,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BlockyConfigEntry) -> bool:
    """Set up a Blocky config entry."""
    config = _entry_config(entry)
    client = BlockyClient(async_get_clientsession(hass), config)
    coordinator = BlockyDataUpdateCoordinator(
        hass,
        entry,
        client,
        int(config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    entry.runtime_data = BlockyRuntimeData(
        client=client,
        coordinator=coordinator,
        device_info=DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Blocky",
            manufacturer="Timwun",
            model="DNS proxy",
            configuration_url=client.base_url,
        ),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration after configuration or option changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BlockyConfigEntry) -> bool:
    """Unload a Blocky config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
