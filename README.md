# Sonarr & Radarr Library

Home Assistant custom integration (HACS-compatible) die twee sensoren toevoegt:

- **`sensor.sonarr_downloaded_seasons`** — aantal gedownloade seizoenen in Sonarr, met per seizoen de serietitel, seizoensnummer, aantal afleveringen en downloaddatum in de attributes.
- **`sensor.radarr_downloaded_movies`** — aantal gedownloade films in Radarr, met per film de titel, jaar, kwaliteit en downloaddatum in de attributes.

De sensoren worden elke 15 minuten ververst.

## Installatie via HACS

1. Ga in HACS naar **Integrations** → menu rechtsboven → **Custom repositories**.
2. Voeg deze repository-URL toe (`https://github.com/Xornop/ha-sonarr-radarr-library`) met categorie **Integration**.
3. Zoek naar "Sonarr & Radarr Library" en installeer.
4. Herstart Home Assistant.
5. Ga naar **Instellingen → Apparaten & diensten → Integratie toevoegen** en zoek "Sonarr & Radarr Library".
6. Vul de URL en API-key van Sonarr en Radarr in (te vinden in Sonarr/Radarr onder **Instellingen → Algemeen**).

## Handmatige installatie

Kopieer de map `custom_components/sonarr_radarr_library` naar de `custom_components`-map van je Home Assistant-configuratie en herstart Home Assistant.

## Voorbeeld attributen

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
```

## Let op: Recorder

Deze attributen kunnen bij grote libraries flink groot worden. Sluit de sensoren uit van langdurige geschiedenis om je database klein te houden, bijvoorbeeld in `configuration.yaml`:

```yaml
recorder:
  exclude:
    entities:
      - sensor.sonarr_downloaded_seasons
      - sensor.radarr_downloaded_movies
```

## Vereisten

- Sonarr v3 API (standaard in alle recente Sonarr-versies)
- Radarr v3 API (standaard in alle recente Radarr-versies)
- Beide moeten vanuit Home Assistant bereikbaar zijn (lokaal netwerk of reverse proxy)
