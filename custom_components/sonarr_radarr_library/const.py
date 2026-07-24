"""Constants for the Sonarr & Radarr Library integration."""
from datetime import timedelta

DOMAIN = "sonarr_radarr_library"

CONF_SONARR_URL = "sonarr_url"
CONF_SONARR_API_KEY = "sonarr_api_key"
CONF_RADARR_URL = "radarr_url"
CONF_RADARR_API_KEY = "radarr_api_key"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

SONARR_COORDINATOR = "sonarr_coordinator"
RADARR_COORDINATOR = "radarr_coordinator"

ATTR_ITEMS = "items"
ATTR_LAST_DOWNLOAD = "last_download"

SONARR_ENDPOINT_STATUS = "/api/v3/system/status"
SONARR_ENDPOINT_SERIES = "/api/v3/series"
SONARR_ENDPOINT_EPISODEFILE = "/api/v3/episodefile"

RADARR_ENDPOINT_STATUS = "/api/v3/system/status"
RADARR_ENDPOINT_MOVIE = "/api/v3/movie"
