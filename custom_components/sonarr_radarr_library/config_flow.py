"""Config & options flow for Sonarr & Radarr Library."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import async_test_all_services
from .const import (
    CONF_MAINTAINERR_NAME,
    CONF_MAINTAINERR_URL,
    CONF_QBIT_API_KEY,
    CONF_QBIT_NAME,
    CONF_QBIT_PASSWORD,
    CONF_QBIT_URL,
    CONF_QBIT_USERNAME,
    CONF_RADARR_API_KEY,
    CONF_RADARR_NAME,
    CONF_RADARR_URL,
    CONF_SONARR_API_KEY,
    CONF_SONARR_NAME,
    CONF_SONARR_URL,
    DEFAULT_MAINTAINERR_NAME,
    DEFAULT_QBIT_NAME,
    DEFAULT_RADARR_NAME,
    DEFAULT_SONARR_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Field <-> which service it belongs to, used to attach a test failure to
# the right field so the error shows up next to it in the form.
_ERROR_FIELD_BY_SERVICE = {
    "sonarr": CONF_SONARR_API_KEY,
    "radarr": CONF_RADARR_API_KEY,
    "maintainerr": CONF_MAINTAINERR_URL,
    "qbittorrent": CONF_QBIT_API_KEY,
}


def _service_schema(defaults: dict[str, Any], include_names: bool) -> dict[Any, Any]:
    """Build the URL/API-key (and optionally name) fields shared by both flows."""
    schema: dict[Any, Any] = {}

    if include_names:
        schema[vol.Optional(CONF_SONARR_NAME, default=defaults.get(CONF_SONARR_NAME, DEFAULT_SONARR_NAME))] = str
    schema[vol.Optional(CONF_SONARR_URL, default=defaults.get(CONF_SONARR_URL, ""))] = str
    schema[vol.Optional(CONF_SONARR_API_KEY, default=defaults.get(CONF_SONARR_API_KEY, ""))] = str

    if include_names:
        schema[vol.Optional(CONF_RADARR_NAME, default=defaults.get(CONF_RADARR_NAME, DEFAULT_RADARR_NAME))] = str
    schema[vol.Optional(CONF_RADARR_URL, default=defaults.get(CONF_RADARR_URL, ""))] = str
    schema[vol.Optional(CONF_RADARR_API_KEY, default=defaults.get(CONF_RADARR_API_KEY, ""))] = str

    if include_names:
        schema[vol.Optional(CONF_MAINTAINERR_NAME, default=defaults.get(CONF_MAINTAINERR_NAME, DEFAULT_MAINTAINERR_NAME))] = str
    schema[vol.Optional(CONF_MAINTAINERR_URL, default=defaults.get(CONF_MAINTAINERR_URL, ""))] = str

    if include_names:
        schema[vol.Optional(CONF_QBIT_NAME, default=defaults.get(CONF_QBIT_NAME, DEFAULT_QBIT_NAME))] = str
    schema[vol.Optional(CONF_QBIT_URL, default=defaults.get(CONF_QBIT_URL, ""))] = str
    schema[vol.Optional(CONF_QBIT_API_KEY, default=defaults.get(CONF_QBIT_API_KEY, ""))] = str
    schema[vol.Optional(CONF_QBIT_USERNAME, default=defaults.get(CONF_QBIT_USERNAME, ""))] = str
    schema[vol.Optional(CONF_QBIT_PASSWORD, default=defaults.get(CONF_QBIT_PASSWORD, ""))] = str

    return schema


async def _validate(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate + test the given config. Returns {field: error_key}, empty if OK."""
    errors: dict[str, str] = {}

    sonarr_url = (data.get(CONF_SONARR_URL) or "").strip()
    sonarr_key = (data.get(CONF_SONARR_API_KEY) or "").strip()
    radarr_url = (data.get(CONF_RADARR_URL) or "").strip()
    radarr_key = (data.get(CONF_RADARR_API_KEY) or "").strip()
    maintainerr_url = (data.get(CONF_MAINTAINERR_URL) or "").strip()
    qbit_url = (data.get(CONF_QBIT_URL) or "").strip()
    qbit_api_key = (data.get(CONF_QBIT_API_KEY) or "").strip()
    qbit_username = (data.get(CONF_QBIT_USERNAME) or "").strip()
    qbit_password = (data.get(CONF_QBIT_PASSWORD) or "").strip()

    if sonarr_url and not sonarr_key:
        errors[CONF_SONARR_API_KEY] = "required_with_url"
    if sonarr_key and not sonarr_url:
        errors[CONF_SONARR_URL] = "required_with_key"
    if radarr_url and not radarr_key:
        errors[CONF_RADARR_API_KEY] = "required_with_url"
    if radarr_key and not radarr_url:
        errors[CONF_RADARR_URL] = "required_with_key"
    if qbit_url and not (qbit_api_key or (qbit_username and qbit_password)):
        errors[CONF_QBIT_API_KEY] = "qbit_auth_required"

    if errors:
        return errors

    if not (sonarr_url or radarr_url or maintainerr_url or qbit_url):
        return {"base": "no_services_configured"}

    session = async_get_clientsession(hass)
    try:
        failures = await async_test_all_services(session, data)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error testing Sonarr/Radarr/Maintainerr")
        return {"base": "unknown"}

    for service, reason in failures.items():
        errors[_ERROR_FIELD_BY_SERVICE[service]] = reason

    return errors


class SonarrRadarrLibraryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup. At least one service must be configured."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await _validate(self.hass, user_input)
            if not errors:
                unique_parts = [
                    (user_input.get(CONF_SONARR_URL) or "").strip(),
                    (user_input.get(CONF_RADARR_URL) or "").strip(),
                    (user_input.get(CONF_MAINTAINERR_URL) or "").strip(),
                    (user_input.get(CONF_QBIT_URL) or "").strip(),
                ]
                await self.async_set_unique_id("|".join(p for p in unique_parts if p))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Sonarr & Radarr Library", data=user_input
                )

        schema = vol.Schema(_service_schema(user_input or {}, include_names=True))
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SonarrRadarrLibraryOptionsFlow:
        return SonarrRadarrLibraryOptionsFlow(config_entry)


class SonarrRadarrLibraryOptionsFlow(config_entries.OptionsFlow):
    """Lets URLs/API keys be edited after setup. Names are set-once (see the user step)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        current = {**self.config_entry.data, **self.config_entry.options}
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await _validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)
            current = user_input

        schema = vol.Schema(_service_schema(current, include_names=False))
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
