"""Button platform for Sonarr & Radarr Library: a 'Test connection' button."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import async_test_all_services
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_LABELS = {
    "sonarr": "Sonarr",
    "radarr": "Radarr",
    "maintainerr": "Maintainerr",
}

ERROR_LABELS = {
    "invalid_auth": "invalid API key",
    "cannot_connect": "unreachable",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the connection-test button for this entry."""
    async_add_entities([TestConnectionButton(entry)])


class TestConnectionButton(ButtonEntity):
    """Press to test every currently configured service; skips the rest."""

    _attr_has_entity_name = True
    _attr_name = "Test connection"
    _attr_icon = "mdi:connection"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_test_connection"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Sonarr & Radarr Library",
        }

    async def async_press(self) -> None:
        hass = self.hass
        session = async_get_clientsession(hass)
        config = {**self._entry.data, **self._entry.options}
        failures = await async_test_all_services(session, config)

        if not failures:
            message = "All configured services connected successfully."
        else:
            lines = [
                f"- {SERVICE_LABELS.get(service, service)}: "
                f"{ERROR_LABELS.get(reason, reason)}"
                for service, reason in failures.items()
            ]
            message = "Connection problem(s) found:\n" + "\n".join(lines)

        _LOGGER.info("Sonarr & Radarr Library connection test: %s", message)
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Sonarr & Radarr Library — connection test",
                "message": message,
                "notification_id": f"{self._entry.entry_id}_connection_test",
            },
        )
