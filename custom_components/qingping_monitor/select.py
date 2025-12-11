"""Select entities for Qingping Monitor settings."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_MAC,
    DOWN_TOPIC_TEMPLATE,
    SETTING_SCREENSAVER,
    SETTING_PM25_STANDARD,
    SETTING_TEMP_UNIT,
    SETTING_PM25_CALIB,
)

_LOGGER = logging.getLogger(__name__)


class QingpingSelect(SelectEntity):
    """Select entity for Qingping settings."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        mac: str,
        device_info: DeviceInfo,
        name: str,
        setting_key: str,
        options: list[str],
        option_map: dict[str, int],
        shared_data: dict[str, Any],
        down_topic: str,
        icon: str | None = None,
    ) -> None:
        """Initialize the select entity."""
        self.hass = hass
        self._mac = mac
        self._setting_key = setting_key
        self._option_map = option_map
        self._reverse_map = {v: k for k, v in option_map.items()}
        self._shared_data = shared_data
        self._down_topic = down_topic
        self._config_id = 0

        self._attr_name = name
        self._attr_unique_id = f"qingping_{mac}_{setting_key}"
        self._attr_device_info = device_info
        self._attr_options = options
        if icon:
            self._attr_icon = icon

    @property
    def available(self) -> bool:
        """Return True if value is available."""
        return self._setting_key in self._shared_data

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        if self._setting_key in self._shared_data:
            device_value = self._shared_data[self._setting_key]
            if device_value in self._reverse_map:
                return self._reverse_map[device_value]
        return None

    async def async_select_option(self, option: str) -> None:
        """Select option."""
        device_value = self._option_map[option]
        self._shared_data[self._setting_key] = device_value
        await self._publish_setting(device_value)
        self.async_write_ha_state()
        _LOGGER.info("%s changed to %s (%s)", self._attr_name, option, device_value)

    async def _publish_setting(self, value: Any) -> None:
        """Publish setting to device."""
        self._config_id += 1
        payload = {
            "id": self._config_id,
            "need_ack": 1,
            "type": "17",
            "setting": {self._setting_key: value},
        }
        payload_str = json.dumps(payload, separators=(",", ":"))
        await mqtt.async_publish(self.hass, self._down_topic, payload_str, qos=0, retain=False)
        _LOGGER.debug("Published %s=%s to %s", self._setting_key, value, self._down_topic)

    async def async_added_to_hass(self) -> None:
        """Subscribe to settings updates."""
        @callback
        def handle_settings_update(event):
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_{self._mac}_settings_updated", handle_settings_update)
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    mac = (entry.options.get(CONF_MAC) or entry.data.get(CONF_MAC) or "").upper()
    if not mac:
        return

    data = hass.data[DOMAIN][entry.entry_id]
    shared_settings = data.get("shared_settings", {})
    shared = data.get("shared")
    
    if not shared:
        return

    down_topic = DOWN_TOPIC_TEMPLATE.format(mac=mac)

    # Screensaver options
    screensaver_options = ["Default", "Current Reading Bounce", "All Readings Rotate", "Clock + Current", "Clock + Rotating"]
    screensaver_map = {"Default": 0, "Current Reading Bounce": 1, "All Readings Rotate": 2, "Clock + Current": 3, "Clock + Rotating": 4}

    # PM2.5 Standard options
    pm25_std_options = ["US EPA", "China"]
    pm25_std_map = {"US EPA": 1, "China": 2}

    # Temperature unit options
    temp_unit_options = ["Celsius", "Fahrenheit"]
    temp_unit_map = {"Celsius": "C", "Fahrenheit": "F"}

    # PM2.5 calibration options
    pm25_calib_options = ["Factory", "Custom"]
    pm25_calib_map = {"Factory": 0, "Custom": 1}

    entities = [
        QingpingSelect(hass, mac, shared.device_info, "Screensaver", SETTING_SCREENSAVER, 
                      screensaver_options, screensaver_map, shared_settings, down_topic, "mdi:monitor"),
        QingpingSelect(hass, mac, shared.device_info, "PM2.5 Standard", SETTING_PM25_STANDARD,
                      pm25_std_options, pm25_std_map, shared_settings, down_topic, "mdi:blur"),
        QingpingSelect(hass, mac, shared.device_info, "Temperature Unit", SETTING_TEMP_UNIT,
                      temp_unit_options, temp_unit_map, shared_settings, down_topic, "mdi:thermometer"),
        QingpingSelect(hass, mac, shared.device_info, "PM2.5 Calibration", SETTING_PM25_CALIB,
                      pm25_calib_options, pm25_calib_map, shared_settings, down_topic, "mdi:tune"),
    ]

    async_add_entities(entities)
    _LOGGER.debug("Qingping select entities ready for %s", mac)
