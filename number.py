"""Number platform for Qingping Monitor integration."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from homeassistant.components import mqtt
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_MAC,
    DOWN_TOPIC_TEMPLATE,
    SETTING_REPORT_INTERVAL,
    SETTING_DISPLAY_OFF_TIME,
    SETTING_AUTO_SLIDE_TIME,
    SETTING_POWER_OFF_TIME,
    SETTING_NIGHT_MODE_START,
    SETTING_NIGHT_MODE_END,
    SETTING_TIMEZONE,
    SETTING_CO2_OFFSET,
    SETTING_CO2_ZOOM,
    SETTING_TEMP_OFFSET,
    SETTING_TEMP_ZOOM,
    SETTING_HUMIDITY_OFFSET,
    SETTING_HUMIDITY_ZOOM,
    SETTING_PM25_OFFSET,
    SETTING_PM25_ZOOM,
    SETTING_PM10_OFFSET,
    SETTING_PM10_ZOOM,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class NumberConfig:
    """Configuration for a number entity."""
    setting_key: str
    name: str
    icon: str
    min_value: float
    max_value: float
    step: float
    unit: str | None
    mode: NumberMode = NumberMode.AUTO


# All number settings - NO defaults, values come from device via Type 28
NUMBER_CONFIGS = [
    # ============ TIMING ============
    NumberConfig(
        setting_key=SETTING_REPORT_INTERVAL,
        name="Update Interval",
        icon="mdi:timer-sync-outline",
        min_value=30,
        max_value=3600,
        step=30,
        unit="s",
        mode=NumberMode.SLIDER,
    ),
    NumberConfig(
        setting_key=SETTING_DISPLAY_OFF_TIME,
        name="Display Timeout",
        icon="mdi:monitor-off",
        min_value=0,
        max_value=3600,
        step=60,
        unit="s",
        mode=NumberMode.SLIDER,
    ),
    NumberConfig(
        setting_key=SETTING_AUTO_SLIDE_TIME,
        name="Auto Slide Time",
        icon="mdi:page-next-outline",
        min_value=30,
        max_value=600,
        step=30,
        unit="s",
        mode=NumberMode.SLIDER,
    ),
    NumberConfig(
        setting_key=SETTING_POWER_OFF_TIME,
        name="Power Off Time",
        icon="mdi:power-sleep",
        min_value=0,
        max_value=3600,
        step=60,
        unit="s",
        mode=NumberMode.SLIDER,
    ),
    # ============ NIGHT MODE ============
    NumberConfig(
        setting_key=SETTING_NIGHT_MODE_START,
        name="Night Mode Start",
        icon="mdi:weather-night",
        min_value=0,
        max_value=1439,
        step=30,
        unit="min",
        mode=NumberMode.BOX,
    ),
    NumberConfig(
        setting_key=SETTING_NIGHT_MODE_END,
        name="Night Mode End",
        icon="mdi:weather-sunny",
        min_value=0,
        max_value=1439,
        step=30,
        unit="min",
        mode=NumberMode.BOX,
    ),
    # ============ TIMEZONE ============
    NumberConfig(
        setting_key=SETTING_TIMEZONE,
        name="Timezone",
        icon="mdi:earth",
        min_value=-12,
        max_value=14,
        step=1,
        unit="h",
        mode=NumberMode.BOX,
    ),
    # ============ CO2 CALIBRATION ============
    NumberConfig(
        setting_key=SETTING_CO2_OFFSET,
        name="CO2 Offset",
        icon="mdi:molecule-co2",
        min_value=-500,
        max_value=500,
        step=10,
        unit="ppm",
        mode=NumberMode.BOX,
    ),
    NumberConfig(
        setting_key=SETTING_CO2_ZOOM,
        name="CO2 Zoom",
        icon="mdi:magnify-plus",
        min_value=-100,
        max_value=100,
        step=1,
        unit="%",
        mode=NumberMode.BOX,
    ),
    # ============ TEMPERATURE CALIBRATION ============
    NumberConfig(
        setting_key=SETTING_TEMP_OFFSET,
        name="Temperature Offset",
        icon="mdi:thermometer-plus",
        min_value=-100,
        max_value=100,
        step=1,
        unit="0.1°C",
        mode=NumberMode.BOX,
    ),
    NumberConfig(
        setting_key=SETTING_TEMP_ZOOM,
        name="Temperature Zoom",
        icon="mdi:thermometer-lines",
        min_value=-100,
        max_value=100,
        step=1,
        unit="%",
        mode=NumberMode.BOX,
    ),
    # ============ HUMIDITY CALIBRATION ============
    NumberConfig(
        setting_key=SETTING_HUMIDITY_OFFSET,
        name="Humidity Offset",
        icon="mdi:water-percent",
        min_value=-200,
        max_value=200,
        step=10,
        unit="0.1%",
        mode=NumberMode.BOX,
    ),
    NumberConfig(
        setting_key=SETTING_HUMIDITY_ZOOM,
        name="Humidity Zoom",
        icon="mdi:water-plus",
        min_value=-100,
        max_value=100,
        step=1,
        unit="%",
        mode=NumberMode.BOX,
    ),
    # ============ PM2.5 CALIBRATION ============
    NumberConfig(
        setting_key=SETTING_PM25_OFFSET,
        name="PM2.5 Offset",
        icon="mdi:blur",
        min_value=-100,
        max_value=100,
        step=1,
        unit="µg/m³",
        mode=NumberMode.BOX,
    ),
    NumberConfig(
        setting_key=SETTING_PM25_ZOOM,
        name="PM2.5 Zoom",
        icon="mdi:blur-linear",
        min_value=-100,
        max_value=100,
        step=1,
        unit="%",
        mode=NumberMode.BOX,
    ),
    # ============ PM10 CALIBRATION ============
    NumberConfig(
        setting_key=SETTING_PM10_OFFSET,
        name="PM10 Offset",
        icon="mdi:blur-radial",
        min_value=-100,
        max_value=100,
        step=1,
        unit="µg/m³",
        mode=NumberMode.BOX,
    ),
    NumberConfig(
        setting_key=SETTING_PM10_ZOOM,
        name="PM10 Zoom",
        icon="mdi:blur-off",
        min_value=-100,
        max_value=100,
        step=1,
        unit="%",
        mode=NumberMode.BOX,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qingping number entities."""
    mac = (entry.options.get(CONF_MAC) or entry.data.get(CONF_MAC) or "").upper()
    
    if not mac:
        _LOGGER.error("No MAC address configured")
        return

    formatted_mac = ":".join(mac[i:i+2] for i in range(0, 12, 2))
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"qingping_{mac}")},
        name=f"Qingping Air Monitor ({formatted_mac})",
        manufacturer="Qingping",
        model="Air Monitor Lite",
    )

    down_topic = DOWN_TOPIC_TEMPLATE.format(mac=mac)
    
    # Get shared data - this is where Type 28 settings are stored
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if mac not in hass.data[DOMAIN]:
        hass.data[DOMAIN][mac] = {}
    shared_data = hass.data[DOMAIN][mac]

    entities = []
    for config in NUMBER_CONFIGS:
        entities.append(
            QingpingNumber(
                hass, mac, device_info, down_topic, entry, shared_data, config
            )
        )

    async_add_entities(entities)
    _LOGGER.debug("Qingping number entities ready for %s (%d entities)", mac, len(entities))


class QingpingNumber(NumberEntity):
    """Number entity for Qingping device settings."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        mac: str,
        device_info: DeviceInfo,
        down_topic: str,
        entry: ConfigEntry,
        shared_data: dict,
        config: NumberConfig,
    ) -> None:
        """Initialize the number entity."""
        self.hass = hass
        self._mac = mac
        self._down_topic = down_topic
        self._entry = entry
        self._shared_data = shared_data
        self._config = config
        
        self._attr_name = config.name
        self._attr_icon = config.icon
        self._attr_native_min_value = config.min_value
        self._attr_native_max_value = config.max_value
        self._attr_native_step = config.step
        self._attr_native_unit_of_measurement = config.unit
        self._attr_mode = config.mode
        self._attr_unique_id = f"qingping_{mac}_{config.setting_key}"
        self._attr_device_info = device_info
        self._config_id = 100

    @property
    def available(self) -> bool:
        """Return True if value is available (received from device)."""
        return self._config.setting_key in self._shared_data

    @property
    def native_value(self) -> float | None:
        """Return the current value from device (shared_data)."""
        return self._shared_data.get(self._config.setting_key)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value and send ONLY this setting to device."""
        new_value = int(value)
        
        # Update shared data immediately for UI feedback
        self._shared_data[self._config.setting_key] = new_value
        
        # Publish ONLY this single setting to device
        await self._publish_setting(new_value)
        
        self.async_write_ha_state()
        _LOGGER.info("%s changed to %d", self._attr_name, new_value)

    async def _publish_setting(self, value: int) -> None:
        """Publish ONLY this single setting to device via MQTT."""
        self._config_id += 1
        
        # Build payload with ONLY this setting
        setting = {self._config.setting_key: value}
        
        # Special case: report_interval also needs collect/pm_sampling
        if self._config.setting_key == SETTING_REPORT_INTERVAL:
            setting["collect_interval"] = value
            setting["pm_sampling_interval"] = value
        
        payload = {
            "id": self._config_id,
            "need_ack": 1,
            "type": "17",
            "setting": setting
        }
        
        try:
            await mqtt.async_publish(
                self.hass, self._down_topic, json.dumps(payload), qos=0, retain=False
            )
            _LOGGER.debug("Published %s=%d to %s", self._config.setting_key, value, self._down_topic)
        except Exception as e:
            _LOGGER.error("Failed to publish setting: %s", e)

