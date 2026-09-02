"""Sensors exposed by the Blocky integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import BlockyDataUpdateCoordinator


@dataclass(frozen=True)
class BlockySensorDefinition:
    """Describe one summary value exposed by Blocky."""

    key: str
    source: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None


SENSOR_DEFINITIONS = (
    BlockySensorDefinition("queries", "queries"),
    BlockySensorDefinition("blocked", "blocked"),
    BlockySensorDefinition("cached", "cached"),
    BlockySensorDefinition("forwarded", "forwarded"),
    BlockySensorDefinition("local", "local"),
    BlockySensorDefinition("filtered", "filtered"),
    BlockySensorDefinition("errors", "errors"),
    BlockySensorDefinition("dropped", "dropped"),
    BlockySensorDefinition(
        "avg_response_ms",
        "avgResponseMs",
        unit="ms",
        device_class=SensorDeviceClass.DURATION,
    ),
    BlockySensorDefinition("cache_hit_rate", "cacheHitRate", unit=PERCENTAGE),
    BlockySensorDefinition("cache_entries", "cache_entries"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blocky sensors."""
    runtime = entry.runtime_data
    async_add_entities(
        BlockySensor(runtime.coordinator, runtime.device_info, entry.entry_id, definition)
        for definition in SENSOR_DEFINITIONS
    )


class BlockySensor(CoordinatorEntity[BlockyDataUpdateCoordinator], SensorEntity):
    """A sensor backed by one value in Blocky's current stats snapshot."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: BlockyDataUpdateCoordinator,
        device_info: Any,
        entry_id: str,
        definition: BlockySensorDefinition,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = SensorEntityDescription(
            key=definition.key,
            translation_key=definition.key,
            native_unit_of_measurement=definition.unit,
            device_class=definition.device_class,
            icon="mdi:chart-line",
        )
        self._definition = definition
        self._attr_unique_id = f"{entry_id}_{definition.key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | float | None:
        """Return the current value without performing I/O."""
        stats = self.coordinator.data.stats
        if not stats:
            return None

        if self._definition.key == "cache_entries":
            cache = stats.get("cache")
            value = cache.get("entries") if isinstance(cache, Mapping) else None
        else:
            summary = stats.get("summary")
            value = (
                summary.get(self._definition.source)
                if isinstance(summary, Mapping)
                else None
            )

        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        if self._definition.key == "cache_hit_rate":
            return value * 100
        return value

    @property
    def available(self) -> bool:
        """Statistics sensors require a successful stats response."""
        return super().available and self.native_value is not None
