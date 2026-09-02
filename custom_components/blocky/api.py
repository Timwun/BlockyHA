"""Async HTTP client for the Blocky REST API."""

from __future__ import annotations

import asyncio
import base64
import json
import re
from collections.abc import Mapping
from typing import Any

import aiohttp
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_BASE_URL,
    CONF_DISABLE_PATH,
    CONF_ENABLE_PATH,
    CONF_LISTS_REFRESH_PATH,
    CONF_STATS_PATH,
    CONF_STATUS_PATH,
    DEFAULT_ENDPOINTS,
    ENDPOINT_DISABLE,
    ENDPOINT_ENABLE,
    ENDPOINT_LISTS_REFRESH,
    ENDPOINT_STATS,
    ENDPOINT_STATUS,
)

REQUEST_TIMEOUT = 10
_DURATION_RE = re.compile(
    r"^(?:(?:\d+(?:\.\d*)?|\.\d+)(?:ns|us|ms|s|m|h))+"
)


class BlockyApiError(Exception):
    """Base exception for Blocky API failures."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class BlockyAuthError(BlockyApiError):
    """The reverse proxy rejected the configured credentials."""


class BlockyConnectionError(BlockyApiError):
    """Blocky could not be reached."""


class BlockyInvalidResponseError(BlockyApiError):
    """Blocky returned an invalid response."""


class BlockyStatsDisabled(BlockyApiError):
    """Blocky statistics are disabled."""


def is_valid_duration(value: str) -> bool:
    """Return whether a value has Blocky's Go duration shape."""
    return bool(_DURATION_RE.fullmatch(value.strip()))


class BlockyClient:
    """Small async client for the configured Blocky endpoints."""

    def __init__(self, session: aiohttp.ClientSession, config: Mapping[str, Any]) -> None:
        self._session = session
        self.base_url = str(config[CONF_BASE_URL]).rstrip("/")
        self._endpoints = {
            CONF_STATUS_PATH: str(
                config.get(CONF_STATUS_PATH, DEFAULT_ENDPOINTS[ENDPOINT_STATUS])
            ),
            CONF_ENABLE_PATH: str(
                config.get(CONF_ENABLE_PATH, DEFAULT_ENDPOINTS[ENDPOINT_ENABLE])
            ),
            CONF_DISABLE_PATH: str(
                config.get(CONF_DISABLE_PATH, DEFAULT_ENDPOINTS[ENDPOINT_DISABLE])
            ),
            CONF_LISTS_REFRESH_PATH: str(
                config.get(
                    CONF_LISTS_REFRESH_PATH,
                    DEFAULT_ENDPOINTS[ENDPOINT_LISTS_REFRESH],
                )
            ),
            CONF_STATS_PATH: str(
                config.get(CONF_STATS_PATH, DEFAULT_ENDPOINTS[ENDPOINT_STATS])
            ),
        }
        username = str(config.get(CONF_USERNAME, ""))
        password = str(config.get(CONF_PASSWORD, ""))
        self._auth_header = (
            "Basic "
            + base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
            if username
            else None
        )

    def _url(self, path: str) -> str:
        """Join a configured path without discarding a reverse-proxy prefix."""
        return f"{self.base_url}/{path.lstrip('/')}"

    async def _request(
        self,
        method: str,
        path_key: str,
        *,
        params: Mapping[str, str] | None = None,
        json_response: bool = False,
    ) -> Any:
        """Perform a request and normalize transport and API errors."""
        headers: dict[str, str] = {}
        if self._auth_header:
            headers["Authorization"] = self._auth_header
        if json_response:
            headers["Accept"] = "application/json"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.request(
                    method,
                    self._url(self._endpoints[path_key]),
                    params=params,
                    headers=headers or None,
                ) as response:
                    body = await response.text()
                    if response.status in (401, 403):
                        raise BlockyAuthError("authentication rejected", response.status)
                    if (
                        response.status == 503
                        and path_key == CONF_STATS_PATH
                        and "statistics are disabled" in body.lower()
                    ):
                        raise BlockyStatsDisabled("statistics are disabled", response.status)
                    if response.status != 200:
                        message = body.strip() or f"HTTP {response.status}"
                        raise BlockyApiError(message[:200], response.status)
                    if not json_response:
                        return None
                    try:
                        return json.loads(body)
                    except (json.JSONDecodeError, TypeError) as err:
                        raise BlockyInvalidResponseError("response was not valid JSON") from err
        except BlockyApiError:
            raise
        except (TimeoutError, aiohttp.ClientError) as err:
            raise BlockyConnectionError("unable to connect to Blocky") from err

    async def get_status(self) -> dict[str, Any]:
        """Fetch and minimally validate the blocking status response."""
        data = await self._request("GET", CONF_STATUS_PATH, json_response=True)
        if not isinstance(data, dict) or not isinstance(data.get("enabled"), bool):
            raise BlockyInvalidResponseError("status response is missing enabled")
        return data

    async def get_stats(self) -> dict[str, Any]:
        """Fetch and minimally validate the statistics response."""
        data = await self._request("GET", CONF_STATS_PATH, json_response=True)
        if not isinstance(data, dict) or not isinstance(data.get("summary"), dict):
            raise BlockyInvalidResponseError("statistics response is missing summary")
        return data

    async def enable_blocking(self) -> None:
        """Enable blocking indefinitely."""
        await self._request("GET", CONF_ENABLE_PATH)

    async def disable_blocking(
        self, duration: str | None = None, groups: str | None = None
    ) -> None:
        """Disable blocking, omitting unset query parameters."""
        params: dict[str, str] = {}
        if duration:
            params["duration"] = duration
        if groups:
            params["groups"] = groups
        await self._request("GET", CONF_DISABLE_PATH, params=params or None)

    async def refresh_lists(self) -> None:
        """Refresh Blocky's configured lists."""
        await self._request("POST", CONF_LISTS_REFRESH_PATH)


async def raise_action_error(
    hass: HomeAssistant, entry: Any, error: BlockyApiError, action: str
) -> None:
    """Translate an API failure raised by an entity or service action."""
    if isinstance(error, BlockyAuthError):
        await entry.async_start_reauth(hass)
        raise HomeAssistantError("Blocky authentication failed") from error
    raise HomeAssistantError(f"Blocky {action} failed: {error.message}") from error
