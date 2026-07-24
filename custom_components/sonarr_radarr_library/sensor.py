"""Sensor platform for Sonarr & Radarr Library."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ITEMS,
    ATTR_LAST_DOWNLOAD,
    DOMAIN,
    RADARR_COORDINATOR,
    SONARR_COORDINATOR,
)
from .coordinator import RadarrDownloadsCoordinator, SonarrDownloadsCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sonarr and Radarr sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            SonarrDownloadedSeasonsSensor(data[SONARR_COORDINATOR], entry),
            RadarrDownloadedMoviesSensor(data[RADARR_COORDINATOR], entry),
        ]
    )


class SonarrDownloadedSeasonsSensor(
    CoordinatorEntity[SonarrDownloadsCoordinator], SensorEntity
):
    """Sensor exposing every downloaded series season known to Sonarr."""

    _attr_has_entity_name = True
    _attr_name = "Sonarr downloaded seasons"
    _attr_icon = "mdi:television-classic"
    _attr_native_unit_of_measurement = "seasons"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: SonarrDownloadsCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_sonarr_downloaded_seasons"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_sonarr")},
            "name": "Sonarr",
            "manufacturer": "Sonarr",
        }

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = self.coordinator.data or []
        return {
            ATTR_ITEMS: items,
            ATTR_LAST_DOWNLOAD: items[0]["download_date"] if items else None,
        }


class RadarrDownloadedMoviesSensor(
    CoordinatorEntity[RadarrDownloadsCoordinator], SensorEntity
):
    """Sensor exposing every downloaded movie known to Radarr."""

    _attr_has_entity_name = True
    _attr_name = "Radarr downloaded movies"
    _attr_icon = "mdi:movie-open"
    _attr_native_unit_of_measurement = "movies"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: RadarrDownloadsCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_radarr_downloaded_movies"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_radarr")},
            "name": "Radarr",
            "manufacturer": "Radarr",
        }

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = self.coordinator.data or []
        return {
            ATTR_ITEMS: items,
            ATTR_LAST_DOWNLOAD: items[0]["download_date"] if items else None,
        }
