"""Data update coordinator for Blocky."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    BlockyApiError,
    BlockyAuthError,
    BlockyClient,
    BlockyConnectionError,
    BlockyStatsDisabled,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BlockyData:
    """The data used by all Blocky entities."""

    status: dict[str, Any]
    stats: dict[str, Any] | None
    stats_error: str | None = None


@dataclass
class BlockyRuntimeData:
    """Runtime objects associated with a config entry."""

    client: BlockyClient
    coordinator: BlockyDataUpdateCoordinator
    device_info: DeviceInfo


class BlockyDataUpdateCoordinator(DataUpdateCoordinator[BlockyData]):
    """Poll Blocky status and statistics with one shared schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: BlockyClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Blocky",
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> BlockyData:
        """Fetch required status and optional statistics."""
        try:
            status = await self.client.get_status()
        except BlockyAuthError as err:
            raise ConfigEntryAuthFailed from err
        except (BlockyConnectionError, BlockyApiError) as err:
            raise UpdateFailed(f"Unable to fetch Blocky status: {err.message}") from err

        try:
            stats = await self.client.get_stats()
        except BlockyStatsDisabled:
            return BlockyData(status=status, stats=None)
        except BlockyAuthError as err:
            raise ConfigEntryAuthFailed from err
        except BlockyApiError as err:
            _LOGGER.debug("Blocky statistics are unavailable: %s", err.message)
            return BlockyData(status=status, stats=None, stats_error=err.message)

        return BlockyData(status=status, stats=stats)
