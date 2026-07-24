"""Minimal async API clients for Sonarr and Radarr (v3 API)."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import async_timeout

from .const import (
    RADARR_ENDPOINT_MOVIE,
    RADARR_ENDPOINT_STATUS,
    SONARR_ENDPOINT_EPISODEFILE,
    SONARR_ENDPOINT_SERIES,
    SONARR_ENDPOINT_STATUS,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30


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

        episode_files = await self._get(SONARR_ENDPOINT_EPISODEFILE)

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
