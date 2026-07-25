"""Constants for the Sonarr & Radarr Library integration."""
from datetime import timedelta

DOMAIN = "sonarr_radarr_library"

CONF_SONARR_URL = "sonarr_url"
CONF_SONARR_API_KEY = "sonarr_api_key"
CONF_RADARR_URL = "radarr_url"
CONF_RADARR_API_KEY = "radarr_api_key"
CONF_MAINTAINERR_URL = "maintainerr_url"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

SONARR_COORDINATOR = "sonarr_coordinator"
RADARR_COORDINATOR = "radarr_coordinator"
MAINTAINERR_COORDINATOR = "maintainerr_coordinator"

ATTR_ITEMS = "items"
ATTR_LAST_DOWNLOAD = "last_download"
ATTR_NEXT_REMOVAL = "next_removal"

SONARR_ENDPOINT_STATUS = "/api/v3/system/status"
SONARR_ENDPOINT_SERIES = "/api/v3/series"
SONARR_ENDPOINT_EPISODEFILE = "/api/v3/episodefile"

RADARR_ENDPOINT_STATUS = "/api/v3/system/status"
RADARR_ENDPOINT_MOVIE = "/api/v3/movie"

# Maintainerr has no authentication at all (by design, per their own docs),
# so there is no API key constant here.
MAINTAINERR_ENDPOINT_HEALTH = "/api/health"
# Powers Maintainerr's own Calendar page, so it carries everything needed
# to compute a scheduled removal date per media item.
MAINTAINERR_ENDPOINT_OVERLAY_DATA = "/api/collections/overlay-data"
