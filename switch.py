"""Switch platform for Qingping Monitor integration."""
from __future__ import annotations

import json
import logging

from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_MAC,
    DOWN_TOPIC_TEMPLATE,
    SETTING_12_HOUR_MODE,
    SETTING_CO2_ASC,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qingping switch entities."""
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
        QingpingSwitch(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_12_HOUR_MODE,
            name="12 Hour Mode",
            icon="mdi:clock-time-twelve",
        ),
        QingpingSwitch(
            hass, mac, device_info, down_topic, shared_data,
            setting_key=SETTING_CO2_ASC,
            name="CO2 Auto Calibration",
            icon="mdi:molecule-co2",
        ),
    ]

    async_add_entities(entities)
    _LOGGER.debug("Qingping switch entities ready for %s", mac)


class QingpingSwitch(SwitchEntity):
    """Switch entity for Qingping device settings."""

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
    ) -> None:
        """Initialize the switch entity."""
        self.hass = hass
        self._mac = mac
        self._down_topic = down_topic
        self._shared_data = shared_data
        self._setting_key = setting_key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"qingping_{mac}_{setting_key}"
        self._attr_device_info = device_info
        self._config_id = 200

    @property
    def available(self) -> bool:
        """Return True if value is available (received from device)."""
        return self._setting_key in self._shared_data

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on (from device data)."""
        if self._setting_key in self._shared_data:
            return bool(self._shared_data[self._setting_key])
        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self._set_value(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._set_value(False)

    async def _set_value(self, value: bool) -> None:
        """Set the switch value and publish ONLY this setting to device."""
        int_value = 1 if value else 0
        
        # Update shared data immediately for UI feedback
        self._shared_data[self._setting_key] = int_value
        
        # Publish ONLY this single setting to device
        await self._publish_setting(int_value)
        
        self.async_write_ha_state()
        _LOGGER.info("%s set to %s", self._attr_name, value)

    async def _publish_setting(self, value: int) -> None:
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
