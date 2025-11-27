"""Select platform for Qingping Monitor integration."""
from __future__ import annotations

import json
import logging

from homeassistant.components import mqtt
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_MAC,
    DOWN_TOPIC_TEMPLATE,
    SETTING_TEMPERATURE_UNIT,
    SETTING_PM25_STANDARD,
    SETTING_SCREENSAVER_TYPE,
    SETTING_PM25_CALIB_MODE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qingping select entities."""
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

    entities = [
        QingpingSelect(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_TEMPERATURE_UNIT,
            name="Temperature Unit",
            icon="mdi:thermometer",
            options=["C", "F"],
            option_map={"C": "C", "F": "F"},
        ),
        QingpingSelect(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_PM25_STANDARD,
            name="PM2.5 Standard",
            icon="mdi:air-filter",
            options=["China", "US EPA", "EU"],
            option_map={"China": 0, "US EPA": 1, "EU": 2},
        ),
        QingpingSelect(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_SCREENSAVER_TYPE,
            name="Screensaver",
            icon="mdi:monitor-shimmer",
            options=["Default", "Current Reading Bounce", "All Readings Rotate", "Clock + Current", "Clock + Rotating"],
            option_map={"Default": 0, "Current Reading Bounce": 1, "All Readings Rotate": 2, "Clock + Current": 3, "Clock + Rotating": 4},
        ),
        QingpingSelect(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_PM25_CALIB_MODE,
            name="PM2.5 Calibration Mode",
            icon="mdi:tune",
            options=["Auto", "Manual", "Factory"],
            option_map={"Auto": 0, "Manual": 1, "Factory": 2},
        ),
    ]

    async_add_entities(entities)
    _LOGGER.debug("Qingping select entities ready for %s", mac)


class QingpingSelect(SelectEntity):
    """Select entity for Qingping device settings."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        mac: str,
        device_info: DeviceInfo,
        down_topic: str,
        shared_data: dict,
        setting_key: str,
        name: str,
        icon: str,
        options: list[str],
        option_map: dict,
    ) -> None:
        """Initialize the select entity."""
        self.hass = hass
        self._mac = mac
        self._down_topic = down_topic
        self._shared_data = shared_data
        self._setting_key = setting_key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_options = options
        self._option_map = option_map
        self._reverse_map = {v: k for k, v in option_map.items()}
        self._attr_unique_id = f"qingping_{mac}_{setting_key}"
        self._attr_device_info = device_info
        self._config_id = 300

    @property
    def available(self) -> bool:
        """Return True if value is available (received from device)."""
        return self._setting_key in self._shared_data

    @property
    def current_option(self) -> str | None:
        """Return the current selected option from device data."""
        if self._setting_key in self._shared_data:
            device_value = self._shared_data[self._setting_key]
            if device_value in self._reverse_map:
                return self._reverse_map[device_value]
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option and send ONLY this setting to device."""
        if option not in self._option_map:
            _LOGGER.error("Invalid option: %s", option)
            return
        
        device_value = self._option_map[option]
        
        # Update shared data immediately for UI feedback
        self._shared_data[self._setting_key] = device_value
        
        # Publish ONLY this single setting to device
        await self._publish_setting(device_value)
        
        self.async_write_ha_state()
        _LOGGER.info("%s set to %s", self._attr_name, option)

    async def _publish_setting(self, value) -> None:
        """Publish ONLY this single setting to device via MQTT."""
        self._config_id += 1
        
        payload = {
            "id": self._config_id,
            "need_ack": 1,
            "type": "17",
            "setting": {
                self._setting_key: value
            }
        }
        
        try:
            await mqtt.async_publish(
                self.hass, self._down_topic, json.dumps(payload), qos=0, retain=False
            )
            _LOGGER.debug("Published %s=%s to %s", self._setting_key, value, self._down_topic)
        except Exception as e:
            _LOGGER.error("Failed to publish setting: %s", e)
