"""Switch entities for Qingping Monitor settings."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_MAC,
    DOWN_TOPIC_TEMPLATE,
    SETTING_12_HOUR,
    SETTING_CO2_ASC,
)

_LOGGER = logging.getLogger(__name__)


class QingpingSwitch(SwitchEntity):
    """Switch entity for Qingping settings."""

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
    ) -> None:
        """Initialize the switch entity."""
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

    @property
    def available(self) -> bool:
        """Return True if value is available."""
        return self._setting_key in self._shared_data

    @property
    def is_on(self) -> bool | None:
        """Return current state."""
        if self._setting_key in self._shared_data:
            return bool(self._shared_data[self._setting_key])
        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on."""
        await self._set_value(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off."""
        await self._set_value(False)

    async def _set_value(self, value: bool) -> None:
        """Set value."""
        int_value = 1 if value else 0
        self._shared_data[self._setting_key] = int_value
        await self._publish_setting(int_value)
        self.async_write_ha_state()
        _LOGGER.info("%s changed to %s", self._attr_name, value)

    async def _publish_setting(self, value: int) -> None:
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
    """Set up switch entities."""
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
        QingpingSwitch(hass, mac, shared.device_info, "12 Hour Mode", SETTING_12_HOUR, shared_settings, down_topic, "mdi:clock-outline"),
        QingpingSwitch(hass, mac, shared.device_info, "CO2 Auto Calibration", SETTING_CO2_ASC, shared_settings, down_topic, "mdi:molecule-co2"),
    ]

    async_add_entities(entities)
    _LOGGER.debug("Qingping switch entities ready for %s", mac)
