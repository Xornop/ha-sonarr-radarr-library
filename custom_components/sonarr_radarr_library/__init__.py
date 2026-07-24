"""The Sonarr & Radarr Library integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RadarrClient, SonarrClient
from .const import (
    CONF_RADARR_API_KEY,
    CONF_RADARR_URL,
    CONF_SONARR_API_KEY,
    CONF_SONARR_URL,
    DOMAIN,
    RADARR_COORDINATOR,
    SONARR_COORDINATOR,
)
from .coordinator import RadarrDownloadsCoordinator, SonarrDownloadsCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sonarr & Radarr Library from a config entry."""
    session = async_get_clientsession(hass)

    sonarr_client = SonarrClient(
        session, entry.data[CONF_SONARR_URL], entry.data[CONF_SONARR_API_KEY]
    )
    radarr_client = RadarrClient(
        session, entry.data[CONF_RADARR_URL], entry.data[CONF_RADARR_API_KEY]
    )

    sonarr_coordinator = SonarrDownloadsCoordinator(hass, sonarr_client)
    radarr_coordinator = RadarrDownloadsCoordinator(hass, radarr_client)

    await sonarr_coordinator.async_config_entry_first_refresh()
    await radarr_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        SONARR_COORDINATOR: sonarr_coordinator,
        RADARR_COORDINATOR: radarr_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options/data change."""
    await hass.config_entries.async_reload(entry.entry_id)
