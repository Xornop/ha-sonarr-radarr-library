"""Minimal async API clients for Sonarr, Radarr (v3 API) and Maintainerr."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
import async_timeout

from .const import (
    CONF_MAINTAINERR_URL,
    CONF_QBIT_API_KEY,
    CONF_QBIT_PASSWORD,
    CONF_QBIT_URL,
    CONF_QBIT_USERNAME,
    CONF_RADARR_API_KEY,
    CONF_RADARR_URL,
    CONF_SONARR_API_KEY,
    CONF_SONARR_URL,
    MAINTAINERR_ENDPOINT_HEALTH,
    MAINTAINERR_ENDPOINT_OVERLAY_DATA,
    QBIT_ENDPOINT_LOGIN,
    QBIT_ENDPOINT_PREFERENCES,
    QBIT_ENDPOINT_TORRENTS,
    RADARR_ENDPOINT_MOVIE,
    RADARR_ENDPOINT_QUEUE,
    RADARR_ENDPOINT_STATUS,
    SONARR_ENDPOINT_EPISODEFILE,
    SONARR_ENDPOINT_QUEUE,
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

    async def _get_all_pages(self, endpoint: str, query: str) -> list[dict[str, Any]]:
        """Page through a paged *arr endpoint (e.g. /queue) and return all records."""
        records: list[dict[str, Any]] = []
        page = 1
        while True:
            data = await self._get(f"{endpoint}?{query}&page={page}")
            page_records = data.get("records", [])
            records.extend(page_records)
            if not page_records or len(records) >= data.get("totalRecords", len(records)):
                break
            page += 1
        return records


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

    async def async_get_queue_map(self) -> dict[str, dict[str, Any]]:
        """Return {infohash_lower: {"title": ..., "media_type": "series"}}.

        This is the actual fix for qBittorrent only knowing a torrent's
        release name: Sonarr's own download queue links each item's
        downloadId (the torrent's info hash) to the series/episode it
        belongs to, since Sonarr is the one that told the download client
        what to grab in the first place.
        """
        records = await self._get_all_pages(
            SONARR_ENDPOINT_QUEUE, "pageSize=200&includeSeries=true&includeEpisode=true"
        )

        result: dict[str, dict[str, Any]] = {}
        for record in records:
            download_id = record.get("downloadId")
            if not download_id:
                continue

            series = record.get("series") or {}
            episode = record.get("episode") or {}
            title = series.get("title") or record.get("title", "Unknown")
            season = episode.get("seasonNumber")
            ep_number = episode.get("episodeNumber")
            if season is not None and ep_number is not None:
                title = f"{title} S{season:02d}E{ep_number:02d}"

            result[download_id.lower()] = {"title": title, "media_type": "series"}

        return result

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

    async def async_get_queue_map(self) -> dict[str, dict[str, Any]]:
        """Return {infohash_lower: {"title": ..., "media_type": "movie"}}.

        Same idea as SonarrClient.async_get_queue_map(): Radarr's queue
        links each item's downloadId (torrent info hash) to the actual
        movie, since Radarr is the one that sent it to the download client.
        """
        records = await self._get_all_pages(
            RADARR_ENDPOINT_QUEUE, "pageSize=200&includeMovie=true"
        )

        result: dict[str, dict[str, Any]] = {}
        for record in records:
            download_id = record.get("downloadId")
            if not download_id:
                continue

            movie = record.get("movie") or {}
            title = movie.get("title") or record.get("title", "Unknown")
            year = movie.get("year")
            if year:
                title = f"{title} ({year})"

            result[download_id.lower()] = {"title": title, "media_type": "movie"}

        return result

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


class QbittorrentClient:
    """Client for qBittorrent's WebUI API.

    qBittorrent itself only ever knows a download's torrent name (e.g.
    "Some.Movie.2024.1080p.WEB-DL-GROUP"), never the actual movie/series it
    belongs to. To resolve that, this client cross-references each
    torrent's info hash against Sonarr's and Radarr's own download queues
    (see SonarrClient/RadarrClient.async_get_queue_map), since those are
    the services that sent the torrent to qBittorrent in the first place
    and already know exactly what it is. Torrents with no match (e.g.
    added outside Sonarr/Radarr) fall back to the raw torrent name.

    Two auth modes, picked automatically based on what's configured:
    - API key (qBittorrent >= 5.2.0): sent as an `Authorization: Bearer`
      header on every request. Stateless, no cookies, no CSRF/Referer
      dance — this is the preferred method when available.
    - username/password: the older cookie-based WebUI login
      (/api/v2/auth/login). Kept as a fallback for qBittorrent < 5.2.0,
      where API keys don't exist yet.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        sonarr_client: SonarrClient | None = None,
        radarr_client: RadarrClient | None = None,
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._api_key = api_key or None
        self._username = username
        self._password = password
        self._sonarr_client = sonarr_client
        self._radarr_client = radarr_client
        self._logged_in = False
        self._global_seeding_time_limit: int | None = None  # minutes, None = unknown

    async def _login(self) -> None:
        """Cookie-based login, only used when no API key is configured."""
        try:
            async with async_timeout.timeout(REQUEST_TIMEOUT):
                resp = await self._session.post(
                    f"{self._url}{QBIT_ENDPOINT_LOGIN}",
                    data={"username": self._username, "password": self._password},
                    # qBittorrent's CSRF protection checks the Referer header
                    # on the login request; without it, login is refused.
                    headers={"Referer": self._url},
                )
                resp.raise_for_status()
                body = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ApiConnectionError(str(err)) from err

        if body.strip() != "Ok.":
            raise ApiAuthError("qBittorrent login rejected (check username/password)")
        self._logged_in = True

    def _auth_headers(self) -> dict[str, str]:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        # Cookie auth needs no explicit header beyond Referer (aiohttp's
        # cookie jar attaches the SID cookie automatically after login).
        return {"Referer": self._url}

    async def _get(self, endpoint: str) -> Any:
        if not self._api_key and not self._logged_in:
            await self._login()
        try:
            async with async_timeout.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(
                    f"{self._url}{endpoint}", headers=self._auth_headers()
                )
                if resp.status in (401, 403):
                    if self._api_key:
                        raise ApiAuthError("qBittorrent rejected the API key")
                    # Session cookie expired; log in again and retry once.
                    self._logged_in = False
                    await self._login()
                    resp = await self._session.get(
                        f"{self._url}{endpoint}", headers=self._auth_headers()
                    )
                resp.raise_for_status()
                return await resp.json()
        except ApiAuthError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ApiConnectionError(str(err)) from err

    async def async_test_connection(self) -> None:
        """Raise ApiAuthError / ApiConnectionError if auth or the connection fails."""
        if self._api_key:
            # API keys can't use /auth/login (it's explicitly excluded), so
            # test with a real, cheap authenticated endpoint instead.
            await self._get(QBIT_ENDPOINT_PREFERENCES)
        else:
            await self._login()

    async def _async_get_global_seeding_time_limit(self) -> int | None:
        """Return qBittorrent's global 'max seeding time' in minutes, or None.

        Per-torrent seeding_time_limit of -2 means "use the global limit",
        so this is needed to turn that into an actual removal estimate.
        Fetched once and cached for the lifetime of this client.
        """
        if self._global_seeding_time_limit is not None:
            return self._global_seeding_time_limit
        try:
            prefs = await self._get(QBIT_ENDPOINT_PREFERENCES)
        except (ApiAuthError, ApiConnectionError):
            return None
        if prefs.get("max_seeding_time_enabled") and prefs.get("max_seeding_time", -1) >= 0:
            self._global_seeding_time_limit = prefs["max_seeding_time"]
        else:
            self._global_seeding_time_limit = -1  # sentinel: checked, no global limit
        return self._global_seeding_time_limit if self._global_seeding_time_limit >= 0 else None

    async def async_get_active_downloads(self) -> list[dict[str, Any]]:
        """Return every torrent currently in qBittorrent, matched to its
        real title via Sonarr/Radarr where possible, with an estimated
        removal date based on qBittorrent's seeding-time limit.
        """
        torrents = await self._get(QBIT_ENDPOINT_TORRENTS)

        title_map: dict[str, dict[str, Any]] = {}
        if self._sonarr_client is not None:
            try:
                sonarr_map = await self._sonarr_client.async_get_queue_map()
                title_map.update(sonarr_map)
                _LOGGER.debug("Sonarr queue: %d matchable entries", len(sonarr_map))
            except (ApiAuthError, ApiConnectionError) as err:
                # Logged as a warning (not debug) on purpose: if this fails
                # silently, every download falls back to "unmatched" with
                # no obvious clue why, which is confusing to debug.
                _LOGGER.warning("Could not resolve titles via Sonarr queue: %s", err)
        if self._radarr_client is not None:
            try:
                radarr_map = await self._radarr_client.async_get_queue_map()
                title_map.update(radarr_map)
                _LOGGER.debug("Radarr queue: %d matchable entries", len(radarr_map))
            except (ApiAuthError, ApiConnectionError) as err:
                _LOGGER.warning("Could not resolve titles via Radarr queue: %s", err)

        downloads = []
        matched_count = 0
        for torrent in torrents:
            match, info_hash = self._match_torrent(torrent, title_map)
            if match:
                matched_count += 1

            downloads.append(
                {
                    "title": match["title"] if match else torrent.get("name", "Unknown"),
                    "media_type": match["media_type"] if match else None,
                    "matched_via_arr": match is not None,
                    "info_hash": info_hash,
                    "torrent_name": torrent.get("name"),
                    "category": torrent.get("category"),
                    "state": torrent.get("state"),
                    "progress_percent": round((torrent.get("progress") or 0) * 100, 1),
                    "added_date": self._epoch_to_iso(torrent.get("added_on")),
                    "completed_date": self._epoch_to_iso(torrent.get("completion_on")),
                    "removal_date": await self._estimate_removal_date(torrent),
                }
            )

        _LOGGER.debug(
            "qBittorrent: %d torrents, %d matched via Sonarr/Radarr, %d title(s) known",
            len(torrents),
            matched_count,
            len(title_map),
        )

        return sorted(downloads, key=lambda item: item["removal_date"] or "9999")

    async def _estimate_removal_date(self, torrent: dict[str, Any]) -> str | None:
        """Estimate when qBittorrent's seeding-time limit will auto-remove
        this torrent. Returns None when it can't be predicted: no
        completion date yet, seeding time unlimited, or the torrent (or
        the global default) instead uses a share-ratio limit, which has no
        fixed date.
        """
        completion_on = torrent.get("completion_on")
        if not completion_on or completion_on <= 0:
            return None

        limit = torrent.get("seeding_time_limit")
        if limit is None:
            return None
        if limit == -2:  # use global default
            limit = await self._async_get_global_seeding_time_limit()
        if limit is None or limit < 0:  # unlimited or unknown
            return None

        removal = datetime.fromtimestamp(completion_on, tz=timezone.utc) + timedelta(
            minutes=limit
        )
        return removal.isoformat()

    @staticmethod
    def _match_torrent(
        torrent: dict[str, Any], title_map: dict[str, dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Match a qBittorrent torrent to a Sonarr/Radarr queue entry.

        qBittorrent's "hash" field is the v1 SHA1 hash for v1-only
        torrents, but for hybrid (v1+v2) torrents it can instead be a
        truncated v2 hash — while Sonarr/Radarr may have recorded the v1
        hash as downloadId (e.g. from the original magnet link). To avoid
        silently matching nothing on hybrid torrents, every hash qBittorrent
        exposes for a torrent is tried, not just "hash".
        """
        candidates = [
            torrent.get("hash"),
            torrent.get("infohash_v1"),
            torrent.get("infohash_v2"),
        ]
        primary_hash = next((h for h in candidates if h), None)
        for candidate in candidates:
            if not candidate:
                continue
            match = title_map.get(candidate.lower())
            if match:
                return match, primary_hash
        return None, primary_hash


        if not value or value <= 0:
            return None
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


async def async_test_all_services(
    session: aiohttp.ClientSession, config: dict[str, Any]
) -> dict[str, str]:
    """Test every service that has enough config filled in to be testable.

    Services left blank (or, for Sonarr/Radarr, missing either the URL or
    the API key) are silently skipped rather than counted as a failure.
    Returns {service_key: "invalid_auth" | "cannot_connect"} for failures
    only — an empty dict means everything configured is reachable.
    """
    results: dict[str, str] = {}

    sonarr_url = (config.get(CONF_SONARR_URL) or "").strip()
    sonarr_key = (config.get(CONF_SONARR_API_KEY) or "").strip()
    if sonarr_url and sonarr_key:
        try:
            await SonarrClient(session, sonarr_url, sonarr_key).async_test_connection()
        except ApiAuthError:
            results["sonarr"] = "invalid_auth"
        except ApiConnectionError:
            results["sonarr"] = "cannot_connect"

    radarr_url = (config.get(CONF_RADARR_URL) or "").strip()
    radarr_key = (config.get(CONF_RADARR_API_KEY) or "").strip()
    if radarr_url and radarr_key:
        try:
            await RadarrClient(session, radarr_url, radarr_key).async_test_connection()
        except ApiAuthError:
            results["radarr"] = "invalid_auth"
        except ApiConnectionError:
            results["radarr"] = "cannot_connect"

    maintainerr_url = (config.get(CONF_MAINTAINERR_URL) or "").strip()
    if maintainerr_url:
        try:
            await MaintainerrClient(session, maintainerr_url).async_test_connection()
        except ApiConnectionError:
            results["maintainerr"] = "cannot_connect"

    qbit_url = (config.get(CONF_QBIT_URL) or "").strip()
    if qbit_url:
        qbit_api_key = (config.get(CONF_QBIT_API_KEY) or "").strip()
        qbit_username = (config.get(CONF_QBIT_USERNAME) or "").strip()
        qbit_password = (config.get(CONF_QBIT_PASSWORD) or "").strip()
        try:
            await QbittorrentClient(
                session, qbit_url, qbit_api_key, qbit_username, qbit_password
            ).async_test_connection()
        except ApiAuthError:
            results["qbittorrent"] = "invalid_auth"
        except ApiConnectionError:
            results["qbittorrent"] = "cannot_connect"

    return results
