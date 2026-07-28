"""Constants for the Sonarr & Radarr Library integration."""
from datetime import timedelta

DOMAIN = "sonarr_radarr_library"

CONF_SONARR_URL = "sonarr_url"
CONF_SONARR_API_KEY = "sonarr_api_key"
CONF_SONARR_NAME = "sonarr_name"
CONF_RADARR_URL = "radarr_url"
CONF_RADARR_API_KEY = "radarr_api_key"
CONF_RADARR_NAME = "radarr_name"
CONF_MAINTAINERR_URL = "maintainerr_url"
CONF_MAINTAINERR_NAME = "maintainerr_name"
CONF_QBIT_URL = "qbittorrent_url"
CONF_QBIT_API_KEY = "qbittorrent_api_key"
CONF_QBIT_USERNAME = "qbittorrent_username"
CONF_QBIT_PASSWORD = "qbittorrent_password"
CONF_QBIT_NAME = "qbittorrent_name"

# Used as the device name (and therefore part of the entity_id/friendly
# name) whenever the user leaves the "name" field blank at setup.
DEFAULT_SONARR_NAME = "Sonarr"
DEFAULT_RADARR_NAME = "Radarr"
DEFAULT_MAINTAINERR_NAME = "Maintainerr"
DEFAULT_QBIT_NAME = "qBittorrent"

# Shown as example/helper text under the URL fields in the config flow.
EXAMPLE_SONARR_URL = "http://homeassistant.local:8989"
EXAMPLE_RADARR_URL = "http://homeassistant.local:7878"
EXAMPLE_MAINTAINERR_URL = "http://homeassistant.local:6246"
EXAMPLE_QBIT_URL = "http://homeassistant.local:8080"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

SONARR_COORDINATOR = "sonarr_coordinator"
RADARR_COORDINATOR = "radarr_coordinator"
MAINTAINERR_COORDINATOR = "maintainerr_coordinator"
QBIT_COORDINATOR = "qbittorrent_coordinator"

ATTR_ITEMS = "items"
ATTR_LAST_DOWNLOAD = "last_download"
ATTR_NEXT_REMOVAL = "next_removal"

SONARR_ENDPOINT_STATUS = "/api/v3/system/status"
SONARR_ENDPOINT_SERIES = "/api/v3/series"
SONARR_ENDPOINT_EPISODEFILE = "/api/v3/episodefile"
# Sonarr's current download queue. This is what maps a qBittorrent info
# hash (downloadId) back to the actual series/episode, since qBittorrent
# itself only knows the torrent's release-name, not the show it belongs to.
SONARR_ENDPOINT_QUEUE = "/api/v3/queue"
# The queue only holds items still downloading/importing; once Sonarr
# finishes importing, the entry disappears from the queue even though the
# torrent may still be sitting in qBittorrent, seeding. History keeps the
# grab record (and therefore the hash->episode link) indefinitely, so it's
# used to fill that gap.
SONARR_ENDPOINT_HISTORY = "/api/v3/history"

RADARR_ENDPOINT_STATUS = "/api/v3/system/status"
RADARR_ENDPOINT_MOVIE = "/api/v3/movie"
# Same idea as Sonarr's queue endpoint, but for movies.
RADARR_ENDPOINT_QUEUE = "/api/v3/queue"
RADARR_ENDPOINT_HISTORY = "/api/v3/history"

# Maintainerr has no authentication at all (by design, per their own docs),
# so there is no API key constant here.
MAINTAINERR_ENDPOINT_HEALTH = "/api/health"
# Powers Maintainerr's own Calendar page, so it carries everything needed
# to compute a scheduled removal date per media item.
MAINTAINERR_ENDPOINT_OVERLAY_DATA = "/api/collections/overlay-data"

QBIT_ENDPOINT_LOGIN = "/api/v2/auth/login"
QBIT_ENDPOINT_TORRENTS = "/api/v2/torrents/info"
QBIT_ENDPOINT_PREFERENCES = "/api/v2/app/preferences"
