# Sonarr & Radarr Library

Home Assistant custom integration (HACS-compatible). All three services are **optional** — configure any combination of Sonarr, Radarr and Maintainerr, as long as at least one is filled in:

- **`sensor.<name>_downloaded_seasons`** *(Sonarr)* — number of downloaded seasons, with per-season series title, season number, episode count and download date in the attributes.
- **`sensor.<name>_downloaded_movies`** *(Radarr)* — number of downloaded movies, with per-movie title, year, quality and download date in the attributes.
- **`sensor.<name>_scheduled_removals`** *(Maintainerr, no API key)* — number of media items scheduled for removal, with per-item title, collection, action and computed removal date.
- **A "Test connection" button** — press it to test every currently configured service; results (including which service failed, if any) show up as a persistent notification. Unconfigured services are skipped.

`<name>` defaults to `sonarr`/`radarr`/`maintainerr`, but you can rename each at setup — see below. Sensors refresh every 15 minutes.

## Installation via HACS

1. In HACS, go to **Integrations** → top-right menu → **Custom repositories**.
2. Add this repository URL (`https://github.com/Xornop/ha-sonarr-radarr-library`) with category **Integration**.
3. Search for "Sonarr & Radarr Library" and install, then restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and search for "Sonarr & Radarr Library".
5. Fill in whichever services you use (leave the rest blank) and, optionally, a custom name per service.

## Changing settings later

Go to the integration's card → **Configure**, to update any URL or API key. Leaving a URL blank there disables that service (as long as at least one stays filled in). The per-service **name** fields are set-once, only available during initial setup — that's what determines the entity_id (e.g. `sensor.sonarr_downloaded_seasons`), and Home Assistant's own entity renaming (via the entity's settings) is the way to change it afterwards.

## About the Maintainerr sensor

Maintainerr's `/api/collections/overlay-data` endpoint (the same data behind its own Calendar page) returns each collection's "Take action after days" setting plus the date each item was added; the scheduled removal date is add date + that number of days.

Media items in that payload carry no title — only `tmdbId` (movies) or `tvdbId` (shows) — so titles are resolved by cross-referencing whatever Radarr/Sonarr libraries are also configured on this same integration entry. If a movie/show isn't found there, or Radarr/Sonarr aren't configured, the title falls back to `TMDB <id>` / `TVDB <id>`.

One thing still a best-effort guess: the exact meaning of every `action` (Maintainerr's internal `arrAction` code) beyond `0`, observed meaning "delete" on a real "Delete Movies" collection — other codes are unconfirmed. Each item keeps the full original payload under `raw` for anyone who wants to check via **Developer Tools → States**.

Maintainerr has **no authentication at all** (intentional on their end, with a warning in their own docs against exposing it publicly) — make sure its URL is only reachable on your local network.

## Manual installation

Copy the `custom_components/sonarr_radarr_library` folder into your Home Assistant configuration's `custom_components` folder and restart Home Assistant.

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

(Adjust the entity IDs if you used custom names at setup.)

## Requirements

- Sonarr v3 API (optional)
- Radarr v3 API (optional)
- Maintainerr, no API key (optional) — any recent version exposing `/api/collections/overlay-data`
- Whichever of these you configure must be reachable from Home Assistant (local network or reverse proxy)
