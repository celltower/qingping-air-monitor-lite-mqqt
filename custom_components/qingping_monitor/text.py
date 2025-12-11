"""Text entities for Qingping Monitor settings."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_MAC,
    DOWN_TOPIC_TEMPLATE,
    SETTING_PAGE_SEQ,
    SETTING_TEMP_LED,
    SETTING_HUMI_LED,
    SETTING_CO2_LED,
    SETTING_PM25_LED,
    SETTING_PM10_LED,
)

_LOGGER = logging.getLogger(__name__)


class QingpingText(TextEntity):
    """Text entity for Qingping settings."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        mac: str,
        device_info: DeviceInfo,
        name: str,
        setting_key: str,
        shared_data: dict[str, Any],
        down_topic: str,
        icon: str | None = None,
        pattern: str | None = None,
    ) -> None:
        """Initialize the text entity."""
        self.hass = hass
        self._mac = mac
        self._setting_key = setting_key
        self._shared_data = shared_data
        self._down_topic = down_topic
        self._config_id = 0

        self._attr_name = name
        self._attr_unique_id = f"qingping_{mac}_{setting_key}"
        self._attr_device_info = device_info
        if icon:
            self._attr_icon = icon
        if pattern:
            self._attr_pattern = pattern

    @property
    def available(self) -> bool:
        """Return True if value is available."""
        return self._setting_key in self._shared_data

    @property
    def native_value(self) -> str | None:
        """Return current value."""
        if self._setting_key in self._shared_data:
            return str(self._shared_data[self._setting_key])
        return None

    async def async_set_value(self, value: str) -> None:
        """Set value."""
        self._shared_data[self._setting_key] = value
        await self._publish_setting(value)
        self.async_write_ha_state()
        _LOGGER.info("%s changed to %s", self._attr_name, value)

    async def _publish_setting(self, value: str) -> None:
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
    """Set up text entities."""
    mac = (entry.options.get(CONF_MAC) or entry.data.get(CONF_MAC) or "").upper()
    if not mac:
        return

    data = hass.data[DOMAIN][entry.entry_id]
    shared_settings = data.get("shared_settings", {})
    shared = data.get("shared")
    
    if not shared:
        return

    down_topic = DOWN_TOPIC_TEMPLATE.format(mac=mac)

    entities = [
        QingpingText(hass, mac, shared.device_info, "Page Sequence", SETTING_PAGE_SEQ, 
                    shared_settings, down_topic, "mdi:view-carousel"),
        QingpingText(hass, mac, shared.device_info, "Temperature LED Thresholds", SETTING_TEMP_LED,
                    shared_settings, down_topic, "mdi:led-on"),
        QingpingText(hass, mac, shared.device_info, "Humidity LED Thresholds", SETTING_HUMI_LED,
                    shared_settings, down_topic, "mdi:led-on"),
        QingpingText(hass, mac, shared.device_info, "CO2 LED Thresholds", SETTING_CO2_LED,
                    shared_settings, down_topic, "mdi:led-on"),
        QingpingText(hass, mac, shared.device_info, "PM2.5 LED Thresholds", SETTING_PM25_LED,
                    shared_settings, down_topic, "mdi:led-on"),
        QingpingText(hass, mac, shared.device_info, "PM10 LED Thresholds", SETTING_PM10_LED,
                    shared_settings, down_topic, "mdi:led-on"),
    ]

    async_add_entities(entities)
    _LOGGER.debug("Qingping text entities ready for %s", mac)
