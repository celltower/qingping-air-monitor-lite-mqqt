"""Text platform for Qingping Monitor integration."""
from __future__ import annotations

import json
import logging
import re

from homeassistant.components import mqtt
from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_MAC,
    DOWN_TOPIC_TEMPLATE,
    SETTING_PAGE_SEQUENCE,
    SETTING_TEMP_LED_TH,
    SETTING_HUMI_LED_TH,
    SETTING_CO2_LED_TH,
    SETTING_PM25_LED_TH,
    SETTING_PM10_LED_TH,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qingping text entities."""
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
        QingpingText(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_PAGE_SEQUENCE,
            name="Page Sequence",
            icon="mdi:page-layout-body",
            pattern=r"^[a-z0-9,]+$",
            max_length=100,
        ),
        QingpingText(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_TEMP_LED_TH,
            name="LED Thresholds Temperature",
            icon="mdi:thermometer-alert",
            pattern=r"^[\d,]+$",
            max_length=50,
        ),
        QingpingText(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_HUMI_LED_TH,
            name="LED Thresholds Humidity",
            icon="mdi:water-alert",
            pattern=r"^[\d,]+$",
            max_length=50,
        ),
        QingpingText(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_CO2_LED_TH,
            name="LED Thresholds CO2",
            icon="mdi:molecule-co2",
            pattern=r"^[\d,]+$",
            max_length=50,
        ),
        QingpingText(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_PM25_LED_TH,
            name="LED Thresholds PM2.5",
            icon="mdi:blur",
            pattern=r"^[\d,]+$",
            max_length=50,
        ),
        QingpingText(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_PM10_LED_TH,
            name="LED Thresholds PM10",
            icon="mdi:blur-radial",
            pattern=r"^[\d,]+$",
            max_length=50,
        ),
    ]

    async_add_entities(entities)
    _LOGGER.debug("Qingping text entities ready for %s", mac)


class QingpingText(TextEntity):
    """Text entity for Qingping device settings."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = TextMode.TEXT

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
        pattern: str,
        max_length: int,
    ) -> None:
        """Initialize the text entity."""
        self.hass = hass
        self._mac = mac
        self._down_topic = down_topic
        self._shared_data = shared_data
        self._setting_key = setting_key
        self._pattern = pattern
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"qingping_{mac}_{setting_key}"
        self._attr_device_info = device_info
        self._attr_native_max = max_length
        self._attr_pattern = pattern
        self._config_id = 400

    @property
    def available(self) -> bool:
        """Return True if value is available (received from device)."""
        return self._setting_key in self._shared_data

    @property
    def native_value(self) -> str | None:
        """Return the current value from device data."""
        if self._setting_key in self._shared_data:
            return str(self._shared_data[self._setting_key])
        return None

    async def async_set_value(self, value: str) -> None:
        """Set the text value and send ONLY this setting to device."""
        # Validate pattern
        if self._pattern and not re.match(self._pattern, value):
            _LOGGER.error("Invalid value for %s: %s (pattern: %s)", self._attr_name, value, self._pattern)
            return
        
        # Update shared data immediately for UI feedback
        self._shared_data[self._setting_key] = value
        
        # Publish ONLY this single setting to device
        await self._publish_setting(value)
        
        self.async_write_ha_state()
        _LOGGER.info("%s changed to %s", self._attr_name, value)

    async def _publish_setting(self, value: str) -> None:
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
