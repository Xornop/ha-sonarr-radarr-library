"""Minimal async API clients for Sonarr, Radarr (v3 API) and Maintainerr."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
import async_timeout

from .const import (
    MAINTAINERR_ENDPOINT_HEALTH,
    MAINTAINERR_ENDPOINT_OVERLAY_DATA,
    RADARR_ENDPOINT_MOVIE,
    RADARR_ENDPOINT_STATUS,
    SONARR_ENDPOINT_EPISODEFILE,
    SONARR_ENDPOINT_SERIES,
    SONARR_ENDPOINT_STATUS,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30


def _first_present(data: dict[str, Any], keys: list[str]) -> Any:
    """Return the first non-None value found under any of the given keys."""
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


class ApiAuthError(Exception):
    """Raised when the API key is rejected."""


class ApiConnectionError(Exception):
    """Raised when the host can't be reached."""


class _BaseArrClient:
    """Shared request logic for Sonarr/Radarr *arr APIs."""

    def __init__(self, session: aiohttp.ClientSession, url: str, api_key: str) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._headers = {"X-Api-Key": api_key}

    async def _get(self, endpoint: str) -> Any:
        try:
            async with async_timeout.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(
                    f"{self._url}{endpoint}", headers=self._headers
                )
                if resp.status == 401:
                    raise ApiAuthError(f"Unauthorized for {endpoint}")
                resp.raise_for_status()
                return await resp.json()
        except ApiAuthError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ApiConnectionError(str(err)) from err

    async def async_test_connection(self, status_endpoint: str) -> None:
        """Raise ApiAuthError / ApiConnectionError if the connection is bad."""
        await self._get(status_endpoint)


class SonarrClient(_BaseArrClient):
    """Client for Sonarr."""

    async def async_test_connection(self) -> None:
        await super().async_test_connection(SONARR_ENDPOINT_STATUS)

    async def async_get_downloaded_seasons(self) -> list[dict[str, Any]]:
        """Return one entry per (series, season) that has at least one episode file."""
        series_list = await self._get(SONARR_ENDPOINT_SERIES)
        series_titles = {series["id"]: series.get("title", "Unknown") for series in series_list}

        # Sonarr's /api/v3/episodefile endpoint requires a seriesId query param
        # (an unfiltered GET returns 400 Bad Request), so fetch per series.
        # Skip series with no files yet to keep the number of calls down.
        episode_files: list[dict[str, Any]] = []
        for series in series_list:
            stats = series.get("statistics") or {}
            if not stats.get("episodeFileCount"):
                continue
            series_files = await self._get(
                f"{SONARR_ENDPOINT_EPISODEFILE}?seriesId={series['id']}"
            )
            episode_files.extend(series_files)

        seasons: dict[tuple[int, int], dict[str, Any]] = {}
        for ep_file in episode_files:
            series_id = ep_file.get("seriesId")
            season_number = ep_file.get("seasonNumber")
            date_added = ep_file.get("dateAdded")
            if series_id is None or season_number is None:
                continue

            key = (series_id, season_number)
            entry = seasons.get(key)
            if entry is None:
                entry = {
                    "series": series_titles.get(series_id, "Unknown"),
                    "season": season_number,
                    "episode_count": 0,
                    "download_date": date_added,
                }
                seasons[key] = entry

            entry["episode_count"] += 1
            if date_added and (
                entry["download_date"] is None or date_added > entry["download_date"]
            ):
                entry["download_date"] = date_added

        return sorted(
            seasons.values(),
            key=lambda item: item["download_date"] or "",
            reverse=True,
        )

    async def async_get_tvdb_title_map(self) -> dict[int, str]:
        """Return {tvdbId: title} for every series known to Sonarr.

        Used to resolve series titles for Maintainerr, whose overlay-data
        payload identifies shows by tvdbId only, with no title field.
        """
        series_list = await self._get(SONARR_ENDPOINT_SERIES)
        return {
            series["tvdbId"]: series.get("title", "Unknown")
            for series in series_list
            if series.get("tvdbId")
        }


class RadarrClient(_BaseArrClient):
    """Client for Radarr."""

    async def async_test_connection(self) -> None:
        await super().async_test_connection(RADARR_ENDPOINT_STATUS)

    async def async_get_downloaded_movies(self) -> list[dict[str, Any]]:
        """Return one entry per movie that has a file on disk."""
        movies = await self._get(RADARR_ENDPOINT_MOVIE)

        downloaded = []
        for movie in movies:
            if not movie.get("hasFile"):
                continue

            movie_file = movie.get("movieFile") or {}
            downloaded.append(
                {
                    "title": movie.get("title", "Unknown"),
                    "year": movie.get("year"),
                    "download_date": movie_file.get("dateAdded"),
                    "quality": (movie_file.get("quality") or {})
                    .get("quality", {})
                    .get("name"),
                }
            )

        return sorted(
            downloaded,
            key=lambda item: item["download_date"] or "",
            reverse=True,
        )

    async def async_get_tmdb_title_map(self) -> dict[int, str]:
        """Return {tmdbId: title} for every movie known to Radarr.

        Used to resolve movie titles for Maintainerr, whose overlay-data
        payload identifies movies by tmdbId only, with no title field.
        """
        movies = await self._get(RADARR_ENDPOINT_MOVIE)
        return {
            movie["tmdbId"]: movie.get("title", "Unknown")
            for movie in movies
            if movie.get("tmdbId")
        }


class MaintainerrClient:
    """Client for Maintainerr.

    Maintainerr has no authentication at all (confirmed in its own docs, with
    a warning against exposing it publicly), so unlike Sonarr/Radarr this
    client never sends an API key.

    Field names below are confirmed against a real /api/collections/overlay-
    data response (Maintainerr doesn't publish this schema in its docs).
    One quirk: media items in that payload carry no title — only tmdbId
    (movies) or tvdbId (shows) — so titles are resolved by cross-referencing
    Radarr's and Sonarr's own libraries, which this integration already
    fetches. If a movie/show isn't in Radarr/Sonarr (or those clients
    weren't provided), the title falls back to "TMDB <id>" / "TVDB <id>".
    A couple of collection-level fields are still not fully pinned down
    (e.g. the meaning of every "arrAction" code beyond 0 = delete, observed
    on a real "Delete Movies" collection), so the raw item dict is kept
    under "raw" for anyone who wants to double check.
    """

    COLLECTION_TITLE_KEYS = ["title", "name"]
    COLLECTION_TYPE_KEYS = ["type", "mediaType"]
    COLLECTION_DAYS_KEYS = ["deleteAfterDays", "amountOfDays", "afterDays", "days"]
    COLLECTION_ACTION_KEYS = ["arrAction", "action", "handler"]
    MEDIA_LIST_KEYS = ["media", "items", "collectionMedia", "medias"]
    ITEM_TITLE_KEYS = ["title", "name"]
    ITEM_ADD_DATE_KEYS = ["addDate", "addedAt", "createdAt", "dateAdded"]
    ITEM_SCHEDULED_DATE_KEYS = [
        "scheduledDate",
        "actionDate",
        "targetDate",
        "countdownDate",
        "removalDate",
    ]

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        radarr_client: RadarrClient | None = None,
        sonarr_client: SonarrClient | None = None,
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._radarr_client = radarr_client
        self._sonarr_client = sonarr_client

    async def _get(self, endpoint: str) -> Any:
        try:
            async with async_timeout.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(f"{self._url}{endpoint}")
                resp.raise_for_status()
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ApiConnectionError(str(err)) from err

    async def async_test_connection(self) -> None:
        """Raise ApiConnectionError if Maintainerr can't be reached."""
        await self._get(MAINTAINERR_ENDPOINT_HEALTH)

    async def async_get_scheduled_removals(self) -> list[dict[str, Any]]:
        """Return media items whose collection has a pending scheduled action."""
        tmdb_map: dict[int, str] = {}
        tvdb_map: dict[int, str] = {}

        if self._radarr_client is not None:
            try:
                tmdb_map = await self._radarr_client.async_get_tmdb_title_map()
            except (ApiAuthError, ApiConnectionError) as err:
                _LOGGER.debug("Could not resolve movie titles via Radarr: %s", err)

        if self._sonarr_client is not None:
            try:
                tvdb_map = await self._sonarr_client.async_get_tvdb_title_map()
            except (ApiAuthError, ApiConnectionError) as err:
                _LOGGER.debug("Could not resolve series titles via Sonarr: %s", err)

        payload = await self._get(MAINTAINERR_ENDPOINT_OVERLAY_DATA)
        # Confirmed: this endpoint returns a plain list of collections. The
        # dict fallback below is only a safety net in case a future
        # Maintainerr version wraps it.
        if isinstance(payload, list):
            collections = payload
        else:
            collections = (payload or {}).get("collections", [])

        scheduled: list[dict[str, Any]] = []
        for collection in collections:
            if collection.get("isActive") is False:
                continue

            days = _first_present(collection, self.COLLECTION_DAYS_KEYS)
            if not isinstance(days, (int, float)) or days <= 0:
                # Mirrors Maintainerr's own Calendar rule: collections
                # without a "Take action after days" value are skipped.
                continue

            collection_title = _first_present(collection, self.COLLECTION_TITLE_KEYS) or "Unknown"
            collection_type = _first_present(collection, self.COLLECTION_TYPE_KEYS)
            action = _first_present(collection, self.COLLECTION_ACTION_KEYS)

            media_list: list[dict[str, Any]] = []
            for key in self.MEDIA_LIST_KEYS:
                if isinstance(collection.get(key), list):
                    media_list = collection[key]
                    break

            for item in media_list:
                tmdb_id = item.get("tmdbId")
                tvdb_id = item.get("tvdbId")

                item_title = _first_present(item, self.ITEM_TITLE_KEYS)
                if not item_title:
                    if collection_type == "movie" and tmdb_id in tmdb_map:
                        item_title = tmdb_map[tmdb_id]
                    elif collection_type == "show" and tvdb_id in tvdb_map:
                        item_title = tvdb_map[tvdb_id]
                    elif tmdb_id:
                        item_title = f"TMDB {tmdb_id}"
                    elif tvdb_id:
                        item_title = f"TVDB {tvdb_id}"
                    else:
                        item_title = "Unknown"

                scheduled_date = _first_present(item, self.ITEM_SCHEDULED_DATE_KEYS)
                add_date = _first_present(item, self.ITEM_ADD_DATE_KEYS)
                if not scheduled_date and add_date:
                    scheduled_date = self._add_days(add_date, days)

                scheduled.append(
                    {
                        "title": item_title,
                        "collection": collection_title,
                        "type": collection_type,
                        "action": action,
                        "add_date": add_date,
                        "days_after_add": days,
                        "scheduled_removal_date": scheduled_date,
                        "size_bytes": item.get("sizeBytes"),
                        "raw": item,
                    }
                )

        return sorted(
            scheduled,
            key=lambda entry: entry["scheduled_removal_date"] or "",
        )

    @staticmethod
    def _add_days(date_value: Any, days: float) -> str | None:
        """Best-effort ISO-8601 date parse + day offset; returns None on failure."""
        if not isinstance(date_value, str):
            return None
        try:
            parsed = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return (parsed + timedelta(days=days)).isoformat()
