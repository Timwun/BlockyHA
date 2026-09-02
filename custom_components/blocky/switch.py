"""Blocking switch for the Blocky integration."""

from __future__ import annotations

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
    """Set up the Blocky blocking switch."""
    runtime = entry.runtime_data
    async_add_entities(
        [BlockyBlockingSwitch(runtime.coordinator, runtime.client, runtime.device_info, entry)]
    )


class BlockyBlockingSwitch(CoordinatorEntity, SwitchEntity):
    """Turn Blocky's global blocking mode on or off."""

    _attr_has_entity_name = True
    _attr_translation_key = "blocking"
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator, client, device_info, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._client = client
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_blocking"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        """Return Blocky's current global blocking state."""
        return self.coordinator.data.status.get("enabled")

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose temporary disable information when Blocky provides it."""
        status = self.coordinator.data.status
        attributes: dict[str, object] = {}
        if status.get("disabledGroups"):
            attributes["disabled_groups"] = status["disabledGroups"]
        if status.get("autoEnableInSec") is not None:
            attributes["auto_enable_in_sec"] = status["autoEnableInSec"]
        return attributes

    async def async_turn_on(self, **kwargs) -> None:
        """Enable blocking."""
        try:
            await self._client.enable_blocking()
        except BlockyApiError as err:
            await raise_action_error(self.hass, self._entry, err, "enable blocking")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable blocking indefinitely."""
        try:
            await self._client.disable_blocking()
        except BlockyApiError as err:
            await raise_action_error(self.hass, self._entry, err, "disable blocking")
        await self.coordinator.async_request_refresh()
