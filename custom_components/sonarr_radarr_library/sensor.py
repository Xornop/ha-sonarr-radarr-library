"""Sensor platform for Sonarr & Radarr Library."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ITEMS,
    ATTR_LAST_DOWNLOAD,
    ATTR_NEXT_REMOVAL,
    CONF_MAINTAINERR_NAME,
    CONF_QBIT_NAME,
    CONF_RADARR_NAME,
    CONF_SONARR_NAME,
    DEFAULT_MAINTAINERR_NAME,
    DEFAULT_QBIT_NAME,
    DEFAULT_RADARR_NAME,
    DEFAULT_SONARR_NAME,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a sensor for each service that's actually configured."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    if SONARR_COORDINATOR in data:
        entities.append(SonarrDownloadedSeasonsSensor(data[SONARR_COORDINATOR], entry))
    if RADARR_COORDINATOR in data:
        entities.append(RadarrDownloadedMoviesSensor(data[RADARR_COORDINATOR], entry))
    if MAINTAINERR_COORDINATOR in data:
        entities.append(
            MaintainerrScheduledRemovalsSensor(data[MAINTAINERR_COORDINATOR], entry)
        )
    if QBIT_COORDINATOR in data:
        entities.append(QbittorrentActiveDownloadsSensor(data[QBIT_COORDINATOR], entry))

    async_add_entities(entities)


class SonarrDownloadedSeasonsSensor(
    CoordinatorEntity[SonarrDownloadsCoordinator], SensorEntity
):
    """Sensor exposing every downloaded series season known to Sonarr."""

    _attr_has_entity_name = True
    # Just the suffix on purpose: has_entity_name prefixes this with the
    # device name (the user's chosen Sonarr name) to build the final
    # friendly name / entity_id, e.g. "Sonarr Downloaded seasons" ->
    # sensor.sonarr_downloaded_seasons — not sensor.sonarr_sonarr_....
    _attr_name = "Downloaded seasons"
    _attr_icon = "mdi:television-classic"
    _attr_native_unit_of_measurement = "seasons"

    def __init__(
        self, coordinator: SonarrDownloadsCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        name = entry.data.get(CONF_SONARR_NAME) or DEFAULT_SONARR_NAME
        self._attr_unique_id = f"{entry.entry_id}_sonarr_downloaded_seasons"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_sonarr")},
            "name": name,
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
    _attr_name = "Downloaded movies"
    _attr_icon = "mdi:movie-open"
    _attr_native_unit_of_measurement = "movies"

    def __init__(
        self, coordinator: RadarrDownloadsCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        name = entry.data.get(CONF_RADARR_NAME) or DEFAULT_RADARR_NAME
        self._attr_unique_id = f"{entry.entry_id}_radarr_downloaded_movies"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_radarr")},
            "name": name,
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


class MaintainerrScheduledRemovalsSensor(
    CoordinatorEntity[MaintainerrCoordinator], SensorEntity
):
    """Sensor exposing media that Maintainerr has scheduled for removal."""

    _attr_has_entity_name = True
    _attr_name = "Scheduled removals"
    _attr_icon = "mdi:trash-can-outline"
    _attr_native_unit_of_measurement = "items"

    def __init__(
        self, coordinator: MaintainerrCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        name = entry.data.get(CONF_MAINTAINERR_NAME) or DEFAULT_MAINTAINERR_NAME
        self._attr_unique_id = f"{entry.entry_id}_maintainerr_scheduled_removals"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_maintainerr")},
            "name": name,
            "manufacturer": "Maintainerr",
        }

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = self.coordinator.data or []
        return {
            ATTR_ITEMS: items,
            ATTR_NEXT_REMOVAL: items[0]["scheduled_removal_date"] if items else None,
        }


class QbittorrentActiveDownloadsSensor(
    CoordinatorEntity[QbittorrentCoordinator], SensorEntity
):
    """Sensor exposing every torrent currently active in qBittorrent,
    matched to its real title via Sonarr/Radarr where possible.
    """

    _attr_has_entity_name = True
    _attr_name = "Active downloads"
    _attr_icon = "mdi:download"
    _attr_native_unit_of_measurement = "downloads"

    def __init__(
        self, coordinator: QbittorrentCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        name = entry.data.get(CONF_QBIT_NAME) or DEFAULT_QBIT_NAME
        self._attr_unique_id = f"{entry.entry_id}_qbittorrent_active_downloads"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_qbittorrent")},
            "name": name,
            "manufacturer": "qBittorrent",
        }

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = self.coordinator.data or []
        return {
            ATTR_ITEMS: items,
            ATTR_NEXT_REMOVAL: items[0]["removal_date"] if items else None,
        }
