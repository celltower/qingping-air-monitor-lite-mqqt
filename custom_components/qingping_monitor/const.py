"""Constants for Qingping Monitor integration."""
from __future__ import annotations

DOMAIN = "qingping_monitor"

# Config keys
CONF_MAC = "mac"
CONF_STATE_TOPIC = "state_topic"
CONF_AVAIL_TOPIC = "availability_topic"

# Developer Portal Login (for full auto-provisioning)
CONF_QINGPING_EMAIL = "qingping_email"
CONF_QINGPING_PASSWORD = "qingping_password"

# MQTT Broker Config
CONF_MQTT_HOST = "mqtt_host"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"

# Legacy Cloud API (for auto-rebind feature)
CONF_API_APP_KEY = "api_app_key"
CONF_API_APP_SECRET = "api_app_secret"
QINGPING_OAUTH_URL = "https://oauth.cleargrass.com/oauth2/token"
QINGPING_API_URL = "https://apis.cleargrass.com/v1/apis"

# MQTT Topic templates
STATE_TOPIC_TEMPLATE = "qingping/{mac}/up"
AVAIL_TOPIC_TEMPLATE = "sensors/qingping/{mac}/availability"
DOWN_TOPIC_TEMPLATE = "qingping/{mac}/down"
DISCOVERY_TOPIC = "qingping/+/up"

# Default settings
DEFAULT_INTERVAL_SECONDS = 60

# Watchdog settings
WATCHDOG_CHECK_INTERVAL = 300  # Check every 5 minutes
WATCHDOG_WARNING_THRESHOLD = 600  # Warn after 10 minutes without data
WATCHDOG_CRITICAL_THRESHOLD = 1800  # Critical after 30 minutes
WATCHDOG_KEEPALIVE_INTERVAL = 240  # Send keepalive every 4 minutes

# Settings keys (Type 28)
SETTING_REPORT_INTERVAL = "report_interval"
SETTING_COLLECT_INTERVAL = "collect_interval"
SETTING_PM_SAMPLING = "pm_sampling_interval"
SETTING_DISPLAY_OFF = "display_off_time"
SETTING_POWER_OFF = "power_off_time"
SETTING_AUTO_SLIDE = "auto_slideing_time"
SETTING_NIGHT_START = "night_mode_start_time"
SETTING_NIGHT_END = "night_mode_end_time"
SETTING_TIMEZONE = "timezone"
SETTING_SCREENSAVER = "screensaver_type"
SETTING_12_HOUR = "is_12_hour_mode"
SETTING_PM25_STANDARD = "pm25_standard"
SETTING_TEMP_UNIT = "temperature_unit"
SETTING_CO2_ASC = "co2_asc"
SETTING_CO2_OFFSET = "co2_offset"
SETTING_CO2_ZOOM = "co2_zoom"
SETTING_PM25_OFFSET = "pm25_offset"
SETTING_PM25_ZOOM = "pm25_zoom"
SETTING_PM10_OFFSET = "pm10_offset"
SETTING_PM10_ZOOM = "pm10_zoom"
SETTING_PM25_CALIB = "pm25_calib_mode"
SETTING_TEMP_OFFSET = "temperature_offset"
SETTING_TEMP_ZOOM = "temperature_zoom"
SETTING_HUMI_OFFSET = "humidity_offset"
SETTING_HUMI_ZOOM = "humidity_zoom"
SETTING_PAGE_SEQ = "page_sequence"
SETTING_TEMP_LED = "temp_led_th"
SETTING_HUMI_LED = "humi_led_th"
SETTING_CO2_LED = "co2_led_th"
SETTING_PM25_LED = "pm25_led_th"
SETTING_PM10_LED = "pm10_led_th"
