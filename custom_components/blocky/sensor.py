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


@dataclass(frozen=True)
class BlockyDetailSensorDefinition:
    """Describe one bounded map exposed as sensor attributes."""

    key: str
    source: str
    attribute: str
    icon: str
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT


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

DETAIL_SENSOR_DEFINITIONS = (
    BlockyDetailSensorDefinition(
        "denylist_entries",
        "denylist",
        "groups",
        "mdi:format-list-bulleted",
    ),
    BlockyDetailSensorDefinition(
        "allowlist_entries",
        "allowlist",
        "groups",
        "mdi:format-list-bulleted",
    ),
    BlockyDetailSensorDefinition(
        "query_types",
        "byQueryType",
        "query_types",
        "mdi:format-list-bulleted-type",
        state_class=None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blocky sensors."""
    runtime = entry.runtime_data
    entities = [
        BlockySensor(runtime.coordinator, runtime.device_info, entry.entry_id, definition)
        for definition in SENSOR_DEFINITIONS
    ]
    entities.extend(
        BlockyDetailSensor(
            runtime.coordinator,
            runtime.device_info,
            entry.entry_id,
            definition,
        )
        for definition in DETAIL_SENSOR_DEFINITIONS
    )
    async_add_entities(entities)


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
            return round(value * 100, 1)
        return value

    @property
    def available(self) -> bool:
        """Statistics sensors require a successful stats response."""
        return super().available and self.native_value is not None


class BlockyDetailSensor(CoordinatorEntity[BlockyDataUpdateCoordinator], SensorEntity):
    """Expose a bounded Blocky map as a total and state attributes."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BlockyDataUpdateCoordinator,
        device_info: Any,
        entry_id: str,
        definition: BlockyDetailSensorDefinition,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = SensorEntityDescription(
            key=definition.key,
            translation_key=definition.key,
            state_class=definition.state_class,
            icon=definition.icon,
        )
        self._definition = definition
        self._attr_unique_id = f"{entry_id}_{definition.key}"
        self._attr_device_info = device_info

    def _values(self) -> dict[str, int] | None:
        """Return numeric values from the configured stats map."""
        stats = self.coordinator.data.stats
        if not stats:
            return None

        if self._definition.source == "byQueryType":
            raw_values = stats.get("byQueryType")
        else:
            lists = stats.get("lists")
            raw_values = lists.get(self._definition.source) if isinstance(lists, Mapping) else None
        if not isinstance(raw_values, Mapping):
            return None

        return {
            str(key): value
            for key, value in raw_values.items()
            if isinstance(value, int) and not isinstance(value, bool)
        }

    @property
    def native_value(self) -> int | None:
        """Return the total entries or number of observed query types."""
        values = self._values()
        if values is None:
            return None
        if self._definition.source == "byQueryType":
            return len(values)
        return sum(values.values())

    @property
    def extra_state_attributes(self) -> dict[str, dict[str, int]]:
        """Return the bounded group or query-type map."""
        values = self._values()
        return (
            {self._definition.attribute: dict(sorted(values.items()))}
            if values is not None
            else {}
        )

    @property
    def available(self) -> bool:
        """Detail sensors require a successful stats response and map."""
        return super().available and self.native_value is not None
