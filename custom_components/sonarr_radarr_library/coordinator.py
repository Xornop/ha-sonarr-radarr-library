"""DataUpdateCoordinators for Sonarr & Radarr Library."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiAuthError, ApiConnectionError, RadarrClient, SonarrClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SonarrDownloadsCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator that polls Sonarr for downloaded seasons."""

    def __init__(self, hass: HomeAssistant, client: SonarrClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_sonarr",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            return await self.client.async_get_downloaded_seasons()
        except ApiAuthError as err:
            raise UpdateFailed(f"Sonarr authentication failed: {err}") from err
        except ApiConnectionError as err:
            raise UpdateFailed(f"Sonarr unreachable: {err}") from err


class RadarrDownloadsCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator that polls Radarr for downloaded movies."""

    def __init__(self, hass: HomeAssistant, client: RadarrClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_radarr",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            return await self.client.async_get_downloaded_movies()
        except ApiAuthError as err:
            raise UpdateFailed(f"Radarr authentication failed: {err}") from err
        except ApiConnectionError as err:
            raise UpdateFailed(f"Radarr unreachable: {err}") from err
