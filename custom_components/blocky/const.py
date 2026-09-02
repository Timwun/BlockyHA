"""Constants for the Blocky integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "blocky"
NAME: Final = "Blocky"

CONF_BASE_URL: Final = "base_url"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_STATUS_PATH: Final = "status_path"
CONF_ENABLE_PATH: Final = "enable_path"
CONF_DISABLE_PATH: Final = "disable_path"
CONF_LISTS_REFRESH_PATH: Final = "lists_refresh_path"
CONF_STATS_PATH: Final = "stats_path"

ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_DURATION: Final = "duration"
ATTR_GROUPS: Final = "groups"

SERVICE_DISABLE_FOR_DURATION: Final = "disable_for_duration"

DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 5
MAX_SCAN_INTERVAL: Final = 3600

ENDPOINT_STATUS: Final = "status"
ENDPOINT_ENABLE: Final = "enable"
ENDPOINT_DISABLE: Final = "disable"
ENDPOINT_LISTS_REFRESH: Final = "lists_refresh"
ENDPOINT_STATS: Final = "stats"

DEFAULT_ENDPOINTS: Final[dict[str, str]] = {
    ENDPOINT_STATUS: "/api/blocking/status",
    ENDPOINT_ENABLE: "/api/blocking/enable",
    ENDPOINT_DISABLE: "/api/blocking/disable",
    ENDPOINT_LISTS_REFRESH: "/api/lists/refresh",
    ENDPOINT_STATS: "/api/stats",
}

ENDPOINT_CONFIG_KEYS: Final[dict[str, str]] = {
    ENDPOINT_STATUS: CONF_STATUS_PATH,
    ENDPOINT_ENABLE: CONF_ENABLE_PATH,
    ENDPOINT_DISABLE: CONF_DISABLE_PATH,
    ENDPOINT_LISTS_REFRESH: CONF_LISTS_REFRESH_PATH,
    ENDPOINT_STATS: CONF_STATS_PATH,
}

PLATFORMS: Final = (Platform.SENSOR, Platform.SWITCH, Platform.BUTTON)
