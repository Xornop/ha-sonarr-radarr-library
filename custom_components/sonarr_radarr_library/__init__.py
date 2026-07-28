"""The Sonarr & Radarr Library integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JellyfinClient, MaintainerrClient, QbittorrentClient, RadarrClient, SonarrClient
from .const import (
    CONF_JELLYFIN_API_KEY,
    CONF_JELLYFIN_URL,
    CONF_JELLYFIN_USERNAME,
    CONF_MAINTAINERR_URL,
    CONF_QBIT_API_KEY,
    CONF_QBIT_PASSWORD,
    CONF_QBIT_URL,
    CONF_QBIT_USERNAME,
    CONF_RADARR_API_KEY,
    CONF_RADARR_URL,
    CONF_SONARR_API_KEY,
    CONF_SONARR_URL,
    DOMAIN,
    MAINTAINERR_COORDINATOR,
    QBIT_COORDINATOR,
    RADARR_COORDINATOR,
    SONARR_COORDINATOR,
)
from .coordinator import (
    MaintainerrCoordinator,
    QbittorrentCoordinator,
    RadarrDownloadsCoordinator,
    SonarrDownloadsCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up whichever of Sonarr/Radarr/Maintainerr are configured.

    All three are optional; at least one is guaranteed by the config flow,
    but any single one (or two) may be missing here after a reconfigure.
    """
    session = async_get_clientsession(hass)
    # entry.options (edited later via the options flow) override entry.data
    # (set once at initial setup) for URLs/API keys.
    config = {**entry.data, **entry.options}

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    sonarr_client: SonarrClient | None = None
    radarr_client: RadarrClient | None = None

    sonarr_url = (config.get(CONF_SONARR_URL) or "").strip()
    sonarr_key = (config.get(CONF_SONARR_API_KEY) or "").strip()
    if sonarr_url and sonarr_key:
        sonarr_client = SonarrClient(session, sonarr_url, sonarr_key)
        sonarr_coordinator = SonarrDownloadsCoordinator(hass, sonarr_client)
        await sonarr_coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id][SONARR_COORDINATOR] = sonarr_coordinator

    radarr_url = (config.get(CONF_RADARR_URL) or "").strip()
    radarr_key = (config.get(CONF_RADARR_API_KEY) or "").strip()
    if radarr_url and radarr_key:
        radarr_client = RadarrClient(session, radarr_url, radarr_key)
        radarr_coordinator = RadarrDownloadsCoordinator(hass, radarr_client)
        await radarr_coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id][RADARR_COORDINATOR] = radarr_coordinator

    maintainerr_url = (config.get(CONF_MAINTAINERR_URL) or "").strip()
    if maintainerr_url:
        jellyfin_url = (config.get(CONF_JELLYFIN_URL) or "").strip()
        jellyfin_client = None
        if jellyfin_url:
            jellyfin_client = JellyfinClient(
                session,
                jellyfin_url,
                (config.get(CONF_JELLYFIN_API_KEY) or "").strip(),
                (config.get(CONF_JELLYFIN_USERNAME) or "").strip(),
            )
        maintainerr_client = MaintainerrClient(
            session,
            maintainerr_url,
            radarr_client=radarr_client,
            sonarr_client=sonarr_client,
            # Adds a last_watched_date per item; Maintainerr itself doesn't
            # expose one. None if Jellyfin isn't configured.
            jellyfin_client=jellyfin_client,
        )
        maintainerr_coordinator = MaintainerrCoordinator(hass, maintainerr_client)
        await maintainerr_coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id][MAINTAINERR_COORDINATOR] = maintainerr_coordinator

    qbit_url = (config.get(CONF_QBIT_URL) or "").strip()
    if qbit_url:
        qbit_client = QbittorrentClient(
            session,
            qbit_url,
            (config.get(CONF_QBIT_API_KEY) or "").strip(),
            (config.get(CONF_QBIT_USERNAME) or "").strip(),
            (config.get(CONF_QBIT_PASSWORD) or "").strip(),
            # Passed through so downloads can be matched to their real
            # title via Sonarr's/Radarr's queue instead of the raw
            # torrent name. Either may be None if not configured.
            sonarr_client=sonarr_client,
            radarr_client=radarr_client,
        )
        qbit_coordinator = QbittorrentCoordinator(hass, qbit_client)
        await qbit_coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id][QBIT_COORDINATOR] = qbit_coordinator

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
