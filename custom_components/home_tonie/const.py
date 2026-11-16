"""Konstanten der Home-Tonie-Integration."""

DOMAIN = "home_tonie"
EVENT_TYPE = "esphome.home_tonie"

SUBENTRY_BOX = "box"
SUBENTRY_FIGURE = "figure"

CONF_ESPHOME_DEVICE_ID = "esphome_device_id"
CONF_PLAYER_ENTITY_ID = "player_entity_id"
CONF_MA_USERNAME = "ma_username"
CONF_MAX_VOLUME = "max_volume"
CONF_VOLUME_STEP = "volume_step"
CONF_UID = "uid"
CONF_MEDIA_URI = "media_uri"
CONF_MODE = "mode"
CONF_COLOR = "color"
CONF_DEFAULT_COLOR = "default_color"

DEFAULT_MAX_VOLUME = 40
DEFAULT_VOLUME_STEP = 3
DEFAULT_BOX_COLOR = (128, 0, 255)  # Lila
MODE_RESTART = "restart"
REMOVAL_DEBOUNCE_S = 1.0
# Nur so lange nach der Pause wird beim gemerkten Titel fortgesetzt.
RESUME_MAX_AGE_S = 1800

LED_OFF = "off"
LED_LOADING = "loading"
LED_PLAYING = "playing"
LED_HOLD = "hold"
LED_PAUSED = "paused"
LED_UNKNOWN = "unknown"
LED_ERROR = "error"
LED_VOLUME = "volume"
