"""Number entities for Qingping Monitor settings."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_MAC,
    DOWN_TOPIC_TEMPLATE,
    SETTING_REPORT_INTERVAL,
    SETTING_COLLECT_INTERVAL,
    SETTING_PM_SAMPLING,
    SETTING_DISPLAY_OFF,
    SETTING_POWER_OFF,
    SETTING_AUTO_SLIDE,
    SETTING_NIGHT_START,
    SETTING_NIGHT_END,
    SETTING_TIMEZONE,
    SETTING_CO2_OFFSET,
    SETTING_CO2_ZOOM,
    SETTING_PM25_OFFSET,
    SETTING_PM25_ZOOM,
    SETTING_PM10_OFFSET,
    SETTING_PM10_ZOOM,
    SETTING_TEMP_OFFSET,
    SETTING_TEMP_ZOOM,
    SETTING_HUMI_OFFSET,
    SETTING_HUMI_ZOOM,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class NumberConfig:
    """Configuration for a number entity."""
    name: str
    setting_key: str
    min_value: float
    max_value: float
    step: float = 1
    unit: str | None = None
    icon: str | None = None
    mode: NumberMode = NumberMode.AUTO


NUMBER_CONFIGS = [
    NumberConfig("Report Interval", SETTING_REPORT_INTERVAL, 30, 3600, 10, "s", "mdi:timer"),
    NumberConfig("Collect Interval", SETTING_COLLECT_INTERVAL, 30, 3600, 10, "s", "mdi:timer"),
    NumberConfig("PM Sampling Interval", SETTING_PM_SAMPLING, 30, 3600, 10, "s", "mdi:timer"),
    NumberConfig("Display Off Time", SETTING_DISPLAY_OFF, 0, 3600, 10, "s", "mdi:monitor"),
    NumberConfig("Power Off Time", SETTING_POWER_OFF, 0, 3600, 60, "s", "mdi:power"),
    NumberConfig("Auto Slide Time", SETTING_AUTO_SLIDE, 1, 600, 1, "s", "mdi:view-carousel"),
    NumberConfig("Night Mode Start", SETTING_NIGHT_START, 0, 1440, 1, "min", "mdi:weather-night"),
    NumberConfig("Night Mode End", SETTING_NIGHT_END, 0, 1440, 1, "min", "mdi:weather-sunny"),
    NumberConfig("Timezone", SETTING_TIMEZONE, -12, 14, 1, None, "mdi:earth"),
    NumberConfig("CO2 Offset", SETTING_CO2_OFFSET, -500, 500, 1, "ppm", "mdi:molecule-co2"),
    NumberConfig("CO2 Zoom", SETTING_CO2_ZOOM, -100, 100, 1, "%", "mdi:molecule-co2"),
    NumberConfig("PM2.5 Offset", SETTING_PM25_OFFSET, -100, 100, 1, "µg/m³", "mdi:blur"),
    NumberConfig("PM2.5 Zoom", SETTING_PM25_ZOOM, -100, 100, 1, "%", "mdi:blur"),
    NumberConfig("PM10 Offset", SETTING_PM10_OFFSET, -100, 100, 1, "µg/m³", "mdi:blur"),
    NumberConfig("PM10 Zoom", SETTING_PM10_ZOOM, -100, 100, 1, "%", "mdi:blur"),
    NumberConfig("Temperature Offset", SETTING_TEMP_OFFSET, -10, 10, 0.1, "°C", "mdi:thermometer"),
    NumberConfig("Temperature Zoom", SETTING_TEMP_ZOOM, -100, 100, 1, "%", "mdi:thermometer"),
    NumberConfig("Humidity Offset", SETTING_HUMI_OFFSET, -20, 20, 1, "%", "mdi:water-percent"),
    NumberConfig("Humidity Zoom", SETTING_HUMI_ZOOM, -100, 100, 1, "%", "mdi:water-percent"),
]


class QingpingNumber(NumberEntity):
    """Number entity for Qingping settings."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        mac: str,
        device_info: DeviceInfo,
        config: NumberConfig,
        shared_data: dict[str, Any],
        down_topic: str,
    ) -> None:
        """Initialize the number entity."""
        self.hass = hass
        self._mac = mac
        self._config = config
        self._shared_data = shared_data
        self._down_topic = down_topic
        self._config_id = 0

        self._attr_name = config.name
        self._attr_unique_id = f"qingping_{mac}_{config.setting_key}"
        self._attr_device_info = device_info
        self._attr_native_min_value = config.min_value
        self._attr_native_max_value = config.max_value
        self._attr_native_step = config.step
        self._attr_native_unit_of_measurement = config.unit
        self._attr_mode = config.mode
        if config.icon:
            self._attr_icon = config.icon

    @property
    def available(self) -> bool:
        """Return True if value is available."""
        return self._config.setting_key in self._shared_data

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self._shared_data.get(self._config.setting_key)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        new_value = int(value) if self._config.step >= 1 else value
        self._shared_data[self._config.setting_key] = new_value
        await self._publish_setting(new_value)
        self.async_write_ha_state()
        _LOGGER.info("%s changed to %s", self._attr_name, new_value)

    async def _publish_setting(self, value: Any) -> None:
        """Publish setting to device."""
        self._config_id += 1
        payload = {
            "id": self._config_id,
            "need_ack": 1,
            "type": "17",
            "setting": {self._config.setting_key: value},
        }
        payload_str = json.dumps(payload, separators=(",", ":"))
        await mqtt.async_publish(self.hass, self._down_topic, payload_str, qos=0, retain=False)
        _LOGGER.debug("Published %s=%s to %s", self._config.setting_key, value, self._down_topic)

    async def async_added_to_hass(self) -> None:
        """Subscribe to settings updates."""
        @callback
        def handle_settings_update(event):
            """Handle settings update event."""
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_{self._mac}_settings_updated", handle_settings_update)
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    mac = (entry.options.get(CONF_MAC) or entry.data.get(CONF_MAC) or "").upper()
    if not mac:
        return

    data = hass.data[DOMAIN][entry.entry_id]
    shared_settings = data.get("shared_settings", {})
    shared = data.get("shared")
    
    if not shared:
        _LOGGER.error("Shared data not found for %s", mac)
        return

    down_topic = DOWN_TOPIC_TEMPLATE.format(mac=mac)

    entities = [
        QingpingNumber(hass, mac, shared.device_info, config, shared_settings, down_topic)
        for config in NUMBER_CONFIGS
    ]

    async_add_entities(entities)
    _LOGGER.debug("Qingping number entities ready for %s (%d entities)", mac, len(entities))
