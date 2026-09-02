"""List refresh button for the Blocky integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import BlockyApiError, raise_action_error


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Blocky list refresh button."""
    runtime = entry.runtime_data
    async_add_entities(
        [BlockyRefreshButton(runtime.coordinator, runtime.client, runtime.device_info, entry)]
    )


class BlockyRefreshButton(CoordinatorEntity, ButtonEntity):
    """Refresh all Blocky lists."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh_lists"
    _attr_icon = "mdi:format-list-checks"

    def __init__(self, coordinator, client, device_info, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_refresh_lists"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Refresh Blocky's lists."""
        try:
            await self._client.refresh_lists()
        except BlockyApiError as err:
            await raise_action_error(self.hass, self._entry, err, "list refresh")
        await self.coordinator.async_request_refresh()
