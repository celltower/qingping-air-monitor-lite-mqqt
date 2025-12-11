"""Button entities for Qingping Monitor integration."""
from __future__ import annotations

import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    CONF_MAC,
    CONF_QINGPING_EMAIL,
    CONF_QINGPING_PASSWORD,
    CONF_MQTT_HOST,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
)
from .developer_api import QingpingDeveloperApi

_LOGGER = logging.getLogger(__name__)


def _format_mac(mac: str) -> str:
    """Format MAC as XX:XX:XX:XX:XX:XX."""
    return ":".join(mac[i:i+2] for i in range(0, 12, 2))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    mac = entry.data.get(CONF_MAC, "")
    
    # Only add reconnect button if we have Qingping credentials
    email = entry.data.get(CONF_QINGPING_EMAIL)
    password = entry.data.get(CONF_QINGPING_PASSWORD)
    
    if email and password:
        async_add_entities([
            QingpingReconnectButton(hass, entry, mac),
        ])
        _LOGGER.debug("Added Reconnect button for %s", mac)
    else:
        _LOGGER.debug("No Qingping credentials, skipping Reconnect button for %s", mac)


class QingpingReconnectButton(ButtonEntity):
    """Button to reconnect/rebind device to cloud config."""

    _attr_has_entity_name = True
    _attr_name = "Reconnect"
    _attr_icon = "mdi:connection"
    _attr_entity_category = EntityCategory.DIAGNOSTIC  # Versteckt unter "Diagnose"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        mac: str,
    ) -> None:
        """Initialize the button."""
        self.hass = hass
        self._entry = entry
        self._mac = mac
        self._attr_unique_id = f"{DOMAIN}_{mac}_reconnect"
        
        # Device info - MUST match sensor.py identifiers!
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"qingping_{mac}")},
            name=f"Qingping Air Monitor ({_format_mac(mac)})",
            manufacturer="Qingping",
            model="Air Monitor Lite (CGDN1)",
        )

    async def async_press(self) -> None:
        """Handle button press - reconnect device."""
        _LOGGER.info("Reconnect button pressed for device %s", self._mac)
        
        # Get credentials from entry data
        email = self._entry.data.get(CONF_QINGPING_EMAIL)
        password = self._entry.data.get(CONF_QINGPING_PASSWORD)
        mqtt_host = self._entry.data.get(CONF_MQTT_HOST, "")
        mqtt_port = self._entry.data.get(CONF_MQTT_PORT, 1883)
        mqtt_user = self._entry.data.get(CONF_MQTT_USERNAME, "")
        mqtt_pass = self._entry.data.get(CONF_MQTT_PASSWORD, "")
        
        if not email or not password:
            _LOGGER.error("Cannot reconnect: No Qingping credentials stored")
            return
        
        # Create API client and login
        api = QingpingDeveloperApi()
        
        try:
            if not await api.login(email, password):
                _LOGGER.error("Reconnect failed: Could not login to Qingping")
                return
            
            _LOGGER.info("Logged in to Qingping, finding config...")
            
            # Find existing config
            configs = await api.get_configs()
            config_id = None
            
            for config in configs:
                product = config.get("product", {})
                if product.get("code") == "CGDN1":
                    network_config = config.get("networkConfig", {})
                    if network_config.get("type") == 1:  # MQTT type
                        mqtt_config = network_config.get("mqttConfig", {})
                        # Check if this config matches our MQTT settings
                        if (mqtt_config.get("host") == mqtt_host and 
                            mqtt_config.get("port") == mqtt_port):
                            config_id = config.get("id")
                            _LOGGER.info("Found matching config: %s (ID: %s)", 
                                       config.get("name"), config_id)
                            break
            
            if not config_id:
                # No matching config found, create new one
                _LOGGER.info("No matching config found, creating new one...")
                config_id = await api.create_mqtt_config(
                    name="Home Assistant Auto-Config",
                    mqtt_host=mqtt_host,
                    mqtt_port=mqtt_port,
                    mqtt_username=mqtt_user,
                    mqtt_password=mqtt_pass,
                )
                
                if not config_id:
                    _LOGGER.error("Reconnect failed: Could not create config")
                    return
            
            # Rebind device (unbind + bind)
            _LOGGER.info("Rebinding device %s to config %s...", self._mac, config_id)
            
            if await api.rebind_device(self._mac, config_id):
                _LOGGER.info("✅ Device %s successfully reconnected!", self._mac)
            else:
                _LOGGER.error("Reconnect failed: rebind_device returned False")
                
        except Exception as e:
            _LOGGER.error("Reconnect error: %s", e)
        finally:
            await api.close()

