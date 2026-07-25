# Sonarr & Radarr Library

Home Assistant custom integration (HACS-compatible) that adds three sensors:

- **`sensor.sonarr_downloaded_seasons`** — number of downloaded seasons in Sonarr, with per-season series title, season number, episode count and download date in the attributes.
- **`sensor.radarr_downloaded_movies`** — number of downloaded movies in Radarr, with per-movie title, year, quality and download date in the attributes.
- **`sensor.maintainerr_scheduled_removals`** *(optional)* — number of media items Maintainerr has scheduled for removal (or another action), with per-item title, collection name, action, and the computed scheduled removal date.

Sensors refresh every 15 minutes.

## Installation via HACS

1. In HACS, go to **Integrations** → top-right menu → **Custom repositories**.
2. Add this repository URL (`https://github.com/Xornop/ha-sonarr-radarr-library`) with category **Integration**.
3. Search for "Sonarr & Radarr Library" and install.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and search for "Sonarr & Radarr Library".
6. Enter the URL and API key for Sonarr and Radarr (found in each app under **Settings → General**).
7. Optional: enter the Maintainerr URL. Maintainerr has **no API key** — leave this blank if you don't use Maintainerr.

## About the Maintainerr sensor

Maintainerr's `/api/collections/overlay-data` endpoint (the same data that powers its own Calendar page) returns each collection's "Take action after days" setting plus the date each item was added; the scheduled removal date is add date + that number of days.

Field names were confirmed against a real response from this endpoint (Maintainerr doesn't publish the schema in its docs, only the UI labels). One quirk worth knowing: media items in that payload carry **no title field** — only `tmdbId` (movies) or `tvdbId` (shows) — so titles are resolved by cross-referencing Radarr's and Sonarr's own libraries, which this integration already fetches for the other two sensors. If a movie/show isn't found there, the title falls back to `TMDB <id>` / `TVDB <id>`.

One thing that's still a best-effort guess: the exact meaning of every `action` (Maintainerr's internal `arrAction` code) beyond `0`, which was observed meaning "delete" on a real "Delete Movies" collection — other codes are unconfirmed. Each item also keeps the full original payload under `raw`, so you can check via **Developer Tools → States** or by opening the Maintainerr URL directly in a browser (no auth needed) if anything looks off.

Also note: Maintainerr has **no authentication at all** (that's intentional on their end, with a warning in their own docs about not exposing it publicly). Make sure the Maintainerr URL is only reachable on your local network.

## Manual installation

Copy the `custom_components/sonarr_radarr_library` folder into your Home Assistant configuration's `custom_components` folder and restart Home Assistant.

## Example attributes

```yaml
sensor.sonarr_downloaded_seasons:
  state: 42
  attributes:
    items:
      - series: "The Bear"
        season: 3
        episode_count: 8
        download_date: "2026-06-14T21:03:00Z"
      - series: "Fallout"
        season: 1
        episode_count: 8
        download_date: "2026-05-02T10:12:00Z"
    last_download: "2026-06-14T21:03:00Z"

sensor.radarr_downloaded_movies:
  state: 187
  attributes:
    items:
      - title: "Dune: Part Two"
        year: 2024
        quality: "Bluray-1080p"
        download_date: "2026-06-20T08:45:00Z"
    last_download: "2026-06-20T08:45:00Z"

sensor.maintainerr_scheduled_removals:
  state: 11
  attributes:
    items:
      - title: "Dune: Part Two"
        collection: "Delete Movies 30 days after download"
        type: "movie"
        action: 0
        add_date: "2026-07-24T22:00:00.000Z"
        days_after_add: 30
        scheduled_removal_date: "2026-08-23T22:00:00+00:00"
        size_bytes: 6943828154
        raw: { ... original Maintainerr item, for verification ... }
    next_removal: "2026-08-23T22:00:00+00:00"
```

## Note: Recorder

These attributes can get sizeable with large libraries. Exclude the sensors from long-term history to keep your database small, e.g. in `configuration.yaml`:

```yaml
recorder:
  exclude:
    entities:
      - sensor.sonarr_downloaded_seasons
      - sensor.radarr_downloaded_movies
      - sensor.maintainerr_scheduled_removals
```

## Requirements

- Sonarr v3 API (standard in all recent Sonarr versions)
- Radarr v3 API (standard in all recent Radarr versions)
- Maintainerr (optional, no API key) — any recent version exposing `/api/collections/overlay-data`
- All of these must be reachable from Home Assistant (local network or reverse proxy)
