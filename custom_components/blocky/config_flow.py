"""Config flow for the Blocky integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import (
    BlockyApiError,
    BlockyAuthError,
    BlockyClient,
    BlockyConnectionError,
    BlockyInvalidResponseError,
    BlockyStatsDisabled,
)
from .const import (
    CONF_BASE_URL,
    CONF_DISABLE_PATH,
    CONF_ENABLE_PATH,
    CONF_LISTS_REFRESH_PATH,
    CONF_SCAN_INTERVAL,
    CONF_STATS_PATH,
    CONF_STATUS_PATH,
    DEFAULT_ENDPOINTS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENDPOINT_CONFIG_KEYS,
    ENDPOINT_DISABLE,
    ENDPOINT_ENABLE,
    ENDPOINT_LISTS_REFRESH,
    ENDPOINT_STATS,
    ENDPOINT_STATUS,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


def normalize_base_url(value: str) -> str:
    """Validate and normalize a Blocky base URL."""
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("base URL must include an http or https scheme")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credentials must be entered separately")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL cannot contain a query or fragment")
    try:
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("port is outside the valid range")
    except ValueError as err:
        raise ValueError("base URL has an invalid port") from err
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def normalize_endpoint_path(value: str) -> str:
    """Validate and normalize a relative API path."""
    value = value.strip()
    if not value:
        raise ValueError("endpoint path cannot be empty")
    if "://" in value or "?" in value or "#" in value:
        raise ValueError("endpoint must be a path without a query or fragment")
    return f"/{value.lstrip('/')}"


def _password_selector() -> TextSelector:
    """Return a password input selector without exposing credentials in the UI."""
    return TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _settings_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the advanced connection form schema."""
    return vol.Schema(
        {
            vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Optional(
                CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")
            ): _password_selector(),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
            ),
            vol.Optional(
                CONF_STATUS_PATH,
                default=defaults.get(CONF_STATUS_PATH, DEFAULT_ENDPOINTS[ENDPOINT_STATUS]),
            ): str,
            vol.Optional(
                CONF_ENABLE_PATH,
                default=defaults.get(CONF_ENABLE_PATH, DEFAULT_ENDPOINTS[ENDPOINT_ENABLE]),
            ): str,
            vol.Optional(
                CONF_DISABLE_PATH,
                default=defaults.get(CONF_DISABLE_PATH, DEFAULT_ENDPOINTS[ENDPOINT_DISABLE]),
            ): str,
            vol.Optional(
                CONF_LISTS_REFRESH_PATH,
                default=defaults.get(
                    CONF_LISTS_REFRESH_PATH,
                    DEFAULT_ENDPOINTS[ENDPOINT_LISTS_REFRESH],
                ),
            ): str,
            vol.Optional(
                CONF_STATS_PATH,
                default=defaults.get(CONF_STATS_PATH, DEFAULT_ENDPOINTS[ENDPOINT_STATS]),
            ): str,
        }
    )


def _full_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Build the reconfigure form schema."""
    schema = dict(_settings_schema(defaults).schema)
    schema[vol.Required(CONF_BASE_URL, default=defaults.get(CONF_BASE_URL, ""))] = str
    return vol.Schema(schema)


def _connection_config(base_url: str, values: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize values from a config flow form."""
    username = str(values.get(CONF_USERNAME, "")).strip()
    password = str(values.get(CONF_PASSWORD, ""))
    if bool(username) != bool(password):
        raise ValueError("username and password must be supplied together")

    config: dict[str, Any] = {
        CONF_BASE_URL: normalize_base_url(base_url),
        CONF_USERNAME: username,
        CONF_PASSWORD: password,
        CONF_SCAN_INTERVAL: int(values.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
    }
    for endpoint, config_key in ENDPOINT_CONFIG_KEYS.items():
        config[config_key] = normalize_endpoint_path(
            str(values.get(config_key, DEFAULT_ENDPOINTS[endpoint]))
        )
    return config


async def _async_validate_connection(
    hass: HomeAssistant, config: Mapping[str, Any]
) -> tuple[str, str] | None:
    """Validate the required read endpoints without invoking mutations."""
    client = BlockyClient(async_get_clientsession(hass), config)
    try:
        await client.get_status()
    except BlockyAuthError:
        return CONF_USERNAME, "invalid_auth"
    except BlockyConnectionError:
        return CONF_BASE_URL, "cannot_connect"
    except BlockyInvalidResponseError:
        return CONF_STATUS_PATH, "invalid_status_response"
    except BlockyApiError:
        return CONF_STATUS_PATH, "invalid_status_path"

    try:
        await client.get_stats()
    except BlockyStatsDisabled:
        return None
    except BlockyAuthError:
        return CONF_USERNAME, "invalid_auth"
    except BlockyConnectionError:
        return CONF_BASE_URL, "cannot_connect"
    except BlockyInvalidResponseError:
        return CONF_STATS_PATH, "invalid_stats_response"
    except BlockyApiError:
        return CONF_STATS_PATH, "invalid_stats_path"
    return None


class BlockyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle setup and reconfiguration of Blocky."""

    VERSION = 1

    def __init__(self) -> None:
        self._base_url: str | None = None
        self._defaults: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Collect the Blocky base URL."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._base_url = normalize_base_url(user_input[CONF_BASE_URL])
            except ValueError:
                errors[CONF_BASE_URL] = "invalid_url"
            else:
                return await self.async_step_settings()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_BASE_URL): str}),
            errors=errors,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Collect optional auth, endpoint, and polling settings."""
        errors: dict[str, str] = {}
        if user_input is not None and self._base_url is not None:
            try:
                config = _connection_config(self._base_url, user_input)
            except (TypeError, ValueError) as err:
                message = str(err)
                if "username" in message or "password" in message:
                    errors[CONF_USERNAME] = "auth_pair"
                else:
                    errors[CONF_STATUS_PATH] = "invalid_endpoint"
            else:
                validation_error = await _async_validate_connection(self.hass, config)
                if validation_error is None:
                    title = urlsplit(config[CONF_BASE_URL]).netloc
                    return self.async_create_entry(title=title, data=config)
                errors[validation_error[0]] = validation_error[1]

        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(user_input or self._defaults),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Update all connection settings without removing the entry."""
        entry = self._get_reconfigure_entry()
        defaults = {**entry.data, **entry.options}
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                config = _connection_config(user_input[CONF_BASE_URL], user_input)
            except (KeyError, TypeError, ValueError) as err:
                message = str(err)
                if "username" in message or "password" in message:
                    errors[CONF_USERNAME] = "auth_pair"
                elif "base URL" in message:
                    errors[CONF_BASE_URL] = "invalid_url"
                else:
                    errors[CONF_STATUS_PATH] = "invalid_endpoint"
            else:
                validation_error = await _async_validate_connection(self.hass, config)
                if validation_error is None:
                    return self.async_update_reload_and_abort(
                        entry, data_updates=config, options={}
                    )
                errors[validation_error[0]] = validation_error[1]

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_full_schema(defaults),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Start reauthentication after a proxy rejects credentials."""
        self._reauth_entry = self._get_reauth_entry()
        self._reauth_data = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Collect and validate replacement Basic Auth credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            config = {**self._reauth_data, **user_input}
            try:
                config[CONF_USERNAME] = str(user_input[CONF_USERNAME]).strip()
                config[CONF_PASSWORD] = str(user_input[CONF_PASSWORD])
                if not config[CONF_USERNAME] or not config[CONF_PASSWORD]:
                    raise ValueError("credentials cannot be empty")
            except (KeyError, ValueError):
                errors[CONF_USERNAME] = "auth_pair"
            else:
                validation_error = await _async_validate_connection(self.hass, config)
                if validation_error is None:
                    return self.async_update_reload_and_abort(
                        self._reauth_entry,
                        data_updates={
                            CONF_USERNAME: config[CONF_USERNAME],
                            CONF_PASSWORD: config[CONF_PASSWORD],
                        },
                    )
                errors[validation_error[0]] = validation_error[1]

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): _password_selector(),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the polling interval options flow."""
        return BlockyOptionsFlowHandler()


class BlockyOptionsFlowHandler(OptionsFlow):
    """Handle optional Blocky settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Configure the polling interval."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        defaults = {
            **self.config_entry.data,
            **self.config_entry.options,
        }
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    )
                }
            ),
        )
