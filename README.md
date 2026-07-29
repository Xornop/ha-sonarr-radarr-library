# Sonarr & Radarr Library

Sonarr, Radarr, Maintainerr and qBittorrent each know a piece of your media library — what's downloaded, what's about to be auto-deleted, what's still seeding — but none of them show it all together, and none of them know whether anyone's actually watched something before it gets removed. This integration pulls all of that into Home Assistant sensors, so a single dashboard card can show exactly what's scheduled for removal, how much space it'll free, and when it was last watched — letting you glance at what's about to disappear and step in if something's still wanted, instead of being surprised after the fact. For example:

<details>
<summary>Example dashboard card (click to expand)</summary>

```yaml
type: custom:html-template-card
ignore_line_breaks: true
content: |
  {% set items = state_attr('sensor.maintainerr_scheduled_removals', 'items') %}
  {% set ns = namespace(total=0) %}
  <table style="width:100%; border-collapse: collapse;">
    <tr>
      <th style="text-align:left; padding:0px;">Item</th>
      <th style="text-align:right; padding:0px;">Grootte</th>
      <th style="text-align:right; padding:0px;">Laatst bekeken</th>
      <th style="text-align:right; padding:0px;">Verwijderdatum</th>
    </tr>
    {% for item in items | sort(attribute='scheduled_removal_date') %}
      {% set gb = (item.size_bytes / 1073741824) | round(2) %}
      {% set ns.total = ns.total + gb %}
      <tr>
        <td style="padding:0px;">{{ item.title }}</td>
        <td style="text-align:right; padding:0px;">{{ gb }} GB</td>
        <td style="text-align:right; padding:1px; opacity:0.7;">
          {% if item.last_watched_date %}
            {{ as_timestamp(item.last_watched_date) | timestamp_custom('%d-%m-%y') }}
          {% else %}
            —
          {% endif %}
        </td>
        <td style="text-align:right; padding:1px; opacity:0.7;">{{ as_timestamp(item.scheduled_removal_date) | timestamp_custom('%d-%m-%y') }}</td>
      </tr>
    {% endfor %}
    <tr style="border-top: 1px solid var(--divider-color); font-weight:bold;">
      <td style="padding:0px;">Totaal ({{ items | length }} films)</td>
      <td style="text-align:right;">{{ ns.total | round(2) }} GB</td>
      <td></td>
      <td></td>
    </tr>
  </table>
```

*(Requires the [html-template-card](https://github.com/PiotrMachowski/Home-Assistant-Lovelace-HTML-Jinja2-Template-card) custom card from HACS.)*

</details>

Home Assistant custom integration (HACS-compatible). All five services are **optional** — configure any combination of Sonarr, Radarr, Maintainerr, qBittorrent and Jellyfin, as long as at least one is filled in:

- **`sensor.<name>_downloaded_seasons`** *(Sonarr)* — number of downloaded seasons, with per-season series title, season number, episode count and download date in the attributes.
- **`sensor.<name>_downloaded_movies`** *(Radarr)* — number of downloaded movies, with per-movie title, year, quality and download date in the attributes.
- **`sensor.<name>_scheduled_removals`** *(Maintainerr, no API key)* — number of media items scheduled for removal, with per-item title, collection, action, size and computed removal date. Also shows a last-watched date per item when Jellyfin is configured (see below).
- **`sensor.<name>_active_downloads`** *(qBittorrent)* — number of torrents currently in qBittorrent, with per-torrent title, media type, size, progress, state and an estimated removal date based on qBittorrent's seeding-time limit. See below for how titles are matched.
- **A "Test connection" button** — press it to test every currently configured service; results (including which service failed, if any) show up as a persistent notification. Unconfigured services are skipped.

`<name>` defaults to `sonarr`/`radarr`/`maintainerr`/`qbittorrent`/`jellyfin`, but you can rename each at setup — see below. Sensors refresh every 15 minutes.

Jellyfin has no sensor of its own — it's only used to enrich the Maintainerr sensor with watch dates, so it has no effect unless Maintainerr is also configured.

## Installation via HACS

1. In HACS, go to **Integrations** → top-right menu → **Custom repositories**.
2. Add this repository URL (`https://github.com/Xornop/ha-sonarr-radarr-library`) with category **Integration**.
3. Search for "Sonarr & Radarr Library" and install, then restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and search for "Sonarr & Radarr Library".
5. Fill in whichever services you use (leave the rest blank) and, optionally, a custom name per service.

## Changing settings later

Go to the integration's card → **Configure**, to update any URL, API key or credentials. Leaving a URL blank there disables that service (as long as at least one stays filled in). The per-service **name** fields are set-once, only available during initial setup — that's what determines the entity_id (e.g. `sensor.sonarr_downloaded_seasons`), and Home Assistant's own entity renaming (via the entity's settings) is the way to change it afterwards.

## About the Maintainerr sensor

Maintainerr's `/api/collections/overlay-data` endpoint (the same data behind its own Calendar page) returns each collection's "Take action after days" setting plus the date each item was added; the scheduled removal date is add date + that number of days.

Media items in that payload carry no title — only `tmdbId` (movies) or `tvdbId` (shows) — so titles are resolved by cross-referencing whatever Radarr/Sonarr libraries are also configured on this same integration entry. If a movie/show isn't found there, or Radarr/Sonarr aren't configured, the title falls back to `TMDB <id>` / `TVDB <id>`.

One thing still a best-effort guess: the exact meaning of every `action` (Maintainerr's internal `arrAction` code) beyond `0`, observed meaning "delete" on a real "Delete Movies" collection — other codes are unconfirmed. Each item keeps the full original payload under `raw` for anyone who wants to check via **Developer Tools → States**.

Confirmed against a real response: this payload has no watch-history data at all (`id`, `collectionId`, `mediaServerId`, `tmdbId`, `tvdbId`, `addDate`, `image_path` only) — Maintainerr fetches that from your media server internally, only to evaluate its own rules, and never exposes it here. That's what the optional Jellyfin connection is for: it fills in `last_watched_date` per item, matched via TMDB/TVDB id.

Maintainerr has **no authentication at all** (intentional on their end, with a warning in their own docs against exposing it publicly) — make sure its URL is only reachable on your local network.

## About the qBittorrent sensor

qBittorrent itself only ever knows a download's torrent name (e.g. `Some.Movie.2024.1080p.WEB-DL-GROUP`), never the actual movie or series it belongs to. To resolve that, each torrent's info hash is cross-referenced against Sonarr's and Radarr's own download queue **and** history — since those are the services that sent the torrent to qBittorrent in the first place and already know exactly what it is:

- The **queue** covers items still downloading/importing.
- **History** (grab events, which Sonarr/Radarr keep indefinitely) covers items that already finished importing and are now just sitting in qBittorrent seeding — these disappear from the queue the moment they're imported, so history is what makes those still resolve to a real title.
- Torrents with no match at all (e.g. added outside Sonarr/Radarr) fall back to the raw torrent name, with `matched_via_arr: false` in the attributes so you can tell the difference. Each item also carries its `info_hash` for troubleshooting.

Sonarr/Radarr aren't required for the sensor to work, but titles won't resolve without at least one of them configured.

**Authentication** — two options, tried in this order:
- **API key** *(preferred, qBittorrent ≥ 5.2.0)* — generate one under qBittorrent's WebUI **Settings**. Stateless, no cookies involved.
- **Username/password** *(fallback for qBittorrent < 5.2.0)* — the older cookie-based WebUI login.

**Removal date** is an estimate based on qBittorrent's seeding-time limit (per-torrent, or the global default when a torrent uses "use global limit"), added to its completion date. It's left blank when that can't be predicted — e.g. unlimited seeding time, or a share-ratio limit instead (which has no fixed date).

## About the Jellyfin connection

Jellyfin has no sensor of its own; it's only queried to fill in `last_watched_date` on the Maintainerr sensor. Configure just a URL and an **API key** (create one under Jellyfin's **Dashboard → API Keys**) — no username needed.

Watch state in Jellyfin is per-user, and there's no single "watched by anyone" endpoint, so every user visible to that API key is queried, and the most recent watch date found across all of them is used per item.

For series specifically, Jellyfin doesn't reliably set a watched date on the Series item itself when only individual episodes were watched, so that's not used — episode-level watch data is fetched instead and grouped back to its parent series, which is more reliable.

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
      - sensor.qbittorrent_active_downloads
```

(Adjust the entity IDs if you used custom names at setup.)

## Requirements

- Sonarr v3 API (optional)
- Radarr v3 API (optional)
- Maintainerr, no API key (optional) — any recent version exposing `/api/collections/overlay-data`
- qBittorrent WebUI (optional) — API key needs ≥ 5.2.0; username/password works on older versions too
- Jellyfin (optional) — an API key with access to the users whose watch history you want reflected
- Whichever of these you configure must be reachable from Home Assistant (local network or reverse proxy)
