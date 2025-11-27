"""Constants for the Qingping Monitor integration."""

DOMAIN = "qingping_monitor"

# MQTT Topic Templates
STATE_TOPIC_TEMPLATE = "qingping/{mac}/up"
DOWN_TOPIC_TEMPLATE = "qingping/{mac}/down"
AVAIL_TOPIC_TEMPLATE = "sensors/qingping/{mac}/availability"
DISCOVERY_TOPIC = "qingping/+/up"

# Config Keys
CONF_MAC = "mac"
CONF_STATE_TOPIC = "state_topic"
CONF_AVAIL_TOPIC = "availability_topic"
CONF_UPDATE_INTERVAL = "update_interval_seconds"

# Interval Settings (in SECONDS)
DEFAULT_INTERVAL_SECONDS = 60
MIN_INTERVAL_SECONDS = 30
MAX_INTERVAL_SECONDS = 3600  # 60 minutes

# ============================================================
# Device Settings Keys (from Type 28)
# ============================================================

# Basic Intervals
SETTING_TEMPERATURE_UNIT = "temperature_unit"
SETTING_REPORT_INTERVAL = "report_interval"
SETTING_COLLECT_INTERVAL = "collect_interval"
SETTING_PM_SAMPLING_INTERVAL = "pm_sampling_interval"

# Display & Power
SETTING_DISPLAY_OFF_TIME = "display_off_time"
SETTING_AUTO_SLIDE_TIME = "auto_slideing_time"  # Note: typo in device firmware
SETTING_POWER_OFF_TIME = "power_off_time"
SETTING_SCREENSAVER_TYPE = "screensaver_type"

# Night Mode
SETTING_NIGHT_MODE_START = "night_mode_start_time"
SETTING_NIGHT_MODE_END = "night_mode_end_time"

# Time & Format
SETTING_TIMEZONE = "timezone"
SETTING_12_HOUR_MODE = "is_12_hour_mode"

# Standards
SETTING_PM25_STANDARD = "pm25_standard"
SETTING_PM25_CALIB_MODE = "pm25_calib_mode"

# CO2 Calibration
SETTING_CO2_ASC = "co2_asc"
SETTING_CO2_OFFSET = "co2_offset"
SETTING_CO2_ZOOM = "co2_zoom"

# Temperature Calibration
SETTING_TEMP_OFFSET = "temperature_offset"
SETTING_TEMP_ZOOM = "temperature_zoom"

# Humidity Calibration
SETTING_HUMIDITY_OFFSET = "humidity_offset"
SETTING_HUMIDITY_ZOOM = "humidity_zoom"

# PM Calibration
SETTING_PM25_OFFSET = "pm25_offset"
SETTING_PM25_ZOOM = "pm25_zoom"
SETTING_PM10_OFFSET = "pm10_offset"
SETTING_PM10_ZOOM = "pm10_zoom"

# Page Sequence
SETTING_PAGE_SEQUENCE = "page_sequence"

# LED Threshold Settings
SETTING_TEMP_LED_TH = "temp_led_th"
SETTING_HUMI_LED_TH = "humi_led_th"
SETTING_CO2_LED_TH = "co2_led_th"
SETTING_PM25_LED_TH = "pm25_led_th"
SETTING_PM10_LED_TH = "pm10_led_th"
