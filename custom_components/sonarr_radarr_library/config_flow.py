"""Config flow for Sonarr & Radarr Library."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ApiAuthError, ApiConnectionError, RadarrClient, SonarrClient
from .const import (
    CONF_RADARR_API_KEY,
    CONF_RADARR_URL,
    CONF_SONARR_API_KEY,
    CONF_SONARR_URL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SONARR_URL, default="http://localhost:8989"): str,
        vol.Required(CONF_SONARR_API_KEY): str,
        vol.Required(CONF_RADARR_URL, default="http://localhost:7878"): str,
        vol.Required(CONF_RADARR_API_KEY): str,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Try to reach both Sonarr and Radarr with the given data. Raises on failure."""
    session = async_get_clientsession(hass)

    sonarr = SonarrClient(session, data[CONF_SONARR_URL], data[CONF_SONARR_API_KEY])
    radarr = RadarrClient(session, data[CONF_RADARR_URL], data[CONF_RADARR_API_KEY])

    await sonarr.async_test_connection()
    await radarr.async_test_connection()


class SonarrRadarrLibraryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sonarr & Radarr Library."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_SONARR_URL]}-{user_input[CONF_RADARR_URL]}"
            )
            self._abort_if_unique_id_configured()

            try:
                await _validate_input(self.hass, user_input)
            except ApiAuthError:
                errors["base"] = "invalid_auth"
            except ApiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Sonarr/Radarr")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Sonarr & Radarr Library", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
