"""Config flow for Qingping Monitor integration."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_MAC,
    CONF_STATE_TOPIC,
    CONF_AVAIL_TOPIC,
    CONF_QINGPING_EMAIL,
    CONF_QINGPING_PASSWORD,
    CONF_MQTT_HOST,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    CONF_API_APP_KEY,
    CONF_API_APP_SECRET,
    STATE_TOPIC_TEMPLATE,
    AVAIL_TOPIC_TEMPLATE,
)
from .developer_api import QingpingDeveloperApi

_LOGGER = logging.getLogger(__name__)
MAC_RE = re.compile(r"^[0-9A-F]{12}$", re.I)


def _norm_mac(s: str) -> str:
    """Normalize MAC address."""
    return s.strip().replace(":", "").replace("-", "").replace(".", "").upper()


def _format_mac(mac: str) -> str:
    """Format MAC as XX:XX:XX:XX:XX:XX."""
    return ":".join(mac[i:i+2] for i in range(0, 12, 2))


class QingpingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Qingping Monitor."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize."""
        self._discovered_devices: dict[str, dict[str, Any]] = {}
        self._developer_api: QingpingDeveloperApi | None = None
        self._cloud_devices: list[dict[str, Any]] = []
        self._mqtt_config: dict[str, Any] = {}
        self._qingping_credentials: dict[str, str] = {}
        self._existing_configs: list[dict[str, Any]] = []
        self._selected_config_id: int | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle initial step - choose setup method."""
        if user_input is not None:
            method = user_input.get("method")
            if method == "auto":
                return await self.async_step_qingping_login()
            elif method == "scan":
                return await self.async_step_discovery()
            else:
                return await self.async_step_manual()
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("method", default="auto"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="auto", label="🚀 Automatic Setup (recommended)"),
                            selector.SelectOptionDict(value="scan", label="🔍 Scan MQTT for devices"),
                            selector.SelectOptionDict(value="manual", label="✏️ Enter MAC manually"),
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }),
            description_placeholders={
                "info": "Automatic setup will configure everything for you!"
            }
        )

    # =========================================================================
    # AUTOMATIC SETUP FLOW
    # =========================================================================

    async def async_step_qingping_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Login to Qingping account."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input.get(CONF_QINGPING_EMAIL, "")
            password = user_input.get(CONF_QINGPING_PASSWORD, "")
            
            # Try to login
            self._developer_api = QingpingDeveloperApi()
            if await self._developer_api.login(email, password):
                self._qingping_credentials = {
                    CONF_QINGPING_EMAIL: email,
                    CONF_QINGPING_PASSWORD: password,
                }
                
                # Load existing configs immediately after login
                _LOGGER.info("Login successful, loading existing configs...")
                all_configs = await self._developer_api.get_configs()
                for config in all_configs:
                    product = config.get("product", {})
                    if product.get("code") == "CGDN1":
                        network_config = config.get("networkConfig", {})
                        if network_config.get("type") == 1:  # MQTT type
                            self._existing_configs.append(config)
                            _LOGGER.info("Found existing config: %s (ID: %s)", 
                                       config.get("name"), config.get("id"))
                
                return await self.async_step_mqtt_config()
            else:
                errors["base"] = "login_failed"
                await self._developer_api.close()
                self._developer_api = None

        return self.async_show_form(
            step_id="qingping_login",
            data_schema=vol.Schema({
                vol.Required(CONF_QINGPING_EMAIL): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
                ),
                vol.Required(CONF_QINGPING_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }),
            errors=errors,
            description_placeholders={
                "info": "Use the same credentials as your Qingping+ or Qingping IoT app"
            }
        )

    async def async_step_mqtt_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Configure MQTT broker."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store user input
            self._mqtt_config = {
                CONF_MQTT_HOST: user_input.get(CONF_MQTT_HOST, ""),
                CONF_MQTT_PORT: user_input.get(CONF_MQTT_PORT, 1883),
                CONF_MQTT_USERNAME: user_input.get(CONF_MQTT_USERNAME, ""),
                CONF_MQTT_PASSWORD: user_input.get(CONF_MQTT_PASSWORD, ""),
            }
            
            # Check if we need to update existing config
            if self._existing_configs:
                cloud_config = self._existing_configs[0]
                cloud_mqtt = cloud_config.get("networkConfig", {}).get("mqttConfig", {})
                
                # Check if user changed any values
                changed = (
                    cloud_mqtt.get("host") != self._mqtt_config.get(CONF_MQTT_HOST) or
                    cloud_mqtt.get("port") != self._mqtt_config.get(CONF_MQTT_PORT) or
                    cloud_mqtt.get("username") != self._mqtt_config.get(CONF_MQTT_USERNAME) or
                    cloud_mqtt.get("password") != self._mqtt_config.get(CONF_MQTT_PASSWORD)
                )
                
                if changed:
                    # User changed something - update the cloud config
                    config_id = cloud_config.get("id")
                    _LOGGER.info("User changed MQTT settings, updating cloud config %s", config_id)
                    
                    success = await self._developer_api.update_mqtt_config(
                        config_id=config_id,
                        name=cloud_config.get("name", "Home Assistant"),
                        mqtt_host=self._mqtt_config.get(CONF_MQTT_HOST, ""),
                        mqtt_port=self._mqtt_config.get(CONF_MQTT_PORT, 1883),
                        mqtt_username=self._mqtt_config.get(CONF_MQTT_USERNAME, ""),
                        mqtt_password=self._mqtt_config.get(CONF_MQTT_PASSWORD, ""),
                    )
                    
                    if not success:
                        errors["base"] = "update_failed"
                        _LOGGER.error("Failed to update cloud config")
                
                # Use the existing config ID
                self._selected_config_id = cloud_config.get("id")
            else:
                # No existing config - will create new one
                self._selected_config_id = None
            
            if not errors:
                return await self.async_step_discover_cloud_devices()

        # Load existing cloud config if available
        if not self._existing_configs and self._developer_api:
            all_configs = await self._developer_api.get_configs()
            for config in all_configs:
                product = config.get("product", {})
                if product.get("code") == "CGDN1":
                    network_config = config.get("networkConfig", {})
                    if network_config.get("type") == 1:
                        self._existing_configs.append(config)
        
        # Set defaults from existing cloud config or HA MQTT
        default_host = ""
        default_port = 1883
        default_user = ""
        default_pass = ""
        config_source = "HA MQTT"
        
        if self._existing_configs:
            # Use values from cloud config
            cloud_config = self._existing_configs[0]
            cloud_mqtt = cloud_config.get("networkConfig", {}).get("mqttConfig", {})
            default_host = cloud_mqtt.get("host", "")
            default_port = cloud_mqtt.get("port", 1883)
            default_user = cloud_mqtt.get("username", "")
            default_pass = cloud_mqtt.get("password", "")
            config_source = f"Cloud Config '{cloud_config.get('name')}'"
            _LOGGER.info("Pre-filling MQTT settings from cloud config: %s", cloud_config.get("name"))
        else:
            # Try to get MQTT config from HA
            mqtt_entry = None
            for entry in self.hass.config_entries.async_entries("mqtt"):
                mqtt_entry = entry
                break
            
            if mqtt_entry:
                default_host = mqtt_entry.data.get("broker", "")
                default_port = mqtt_entry.data.get("port", 1883)
                default_user = mqtt_entry.data.get("username", "")

        return self.async_show_form(
            step_id="mqtt_config",
            data_schema=vol.Schema({
                vol.Required(CONF_MQTT_HOST, default=default_host): selector.TextSelector(),
                vol.Required(CONF_MQTT_PORT, default=default_port): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=65535, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_MQTT_USERNAME, default=default_user): selector.TextSelector(),
                vol.Optional(CONF_MQTT_PASSWORD, default=default_pass): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }),
            errors=errors,
            description_placeholders={
                "info": f"Pre-filled from: {config_source}. You can change these values if needed.",
            }
        )

    async def async_step_discover_cloud_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Discover devices from cloud."""
        if not self._developer_api:
            return self.async_abort(reason="not_logged_in")

        # Get devices from cloud
        _LOGGER.info("Fetching devices from Qingping cloud...")
        
        # Get both bound and unbound devices
        unbound = await self._developer_api.get_unbound_air_monitors()
        bound = await self._developer_api.get_bound_air_monitors()
        
        all_devices = []
        
        for device in unbound:
            device["_status"] = "unbound"
            all_devices.append(device)
            
        for device in bound:
            device["_status"] = "bound"
            all_devices.append(device)
        
        self._cloud_devices = all_devices
        
        if not all_devices:
            _LOGGER.warning("No devices found in cloud, showing rescan options")
            return await self.async_step_no_devices()
        
        return await self.async_step_select_devices()

    async def async_step_no_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle no devices found."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "rescan":
                # Rescan for devices
                _LOGGER.info("User requested rescan")
                return await self.async_step_discover_cloud_devices()
            elif action == "scan_mqtt":
                # Switch to MQTT scan
                _LOGGER.info("User switched to MQTT scan")
                if self._developer_api:
                    await self._developer_api.close()
                    self._developer_api = None
                return await self.async_step_discovery()
            elif action == "manual":
                # Switch to manual entry
                _LOGGER.info("User switched to manual entry")
                if self._developer_api:
                    await self._developer_api.close()
                    self._developer_api = None
                return await self.async_step_manual()
            else:
                # Cancel
                _LOGGER.info("User cancelled setup")
                if self._developer_api:
                    await self._developer_api.close()
                return self.async_abort(reason="no_devices")
        
        # Show options with error message
        _LOGGER.info("Showing no_devices step with rescan options")
        return self.async_show_form(
            step_id="no_devices",
            data_schema=vol.Schema({
                vol.Required("action", default="rescan"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="rescan", label="🔄 Rescan Cloud"),
                            selector.SelectOptionDict(value="scan_mqtt", label="🔍 Scan MQTT instead"),
                            selector.SelectOptionDict(value="manual", label="✏️ Enter MAC manually"),
                            selector.SelectOptionDict(value="cancel", label="❌ Cancel"),
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }),
            errors={"base": "no_devices_in_cloud"},
            description_placeholders={
                "info": "No Air Monitor Lite devices found. Make sure device is paired in Qingping+ app."
            }
        )

    async def async_step_select_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Select which devices to set up."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_macs = user_input.get("devices", [])
            
            if not selected_macs:
                errors["base"] = "no_device_selected"
            else:
                # Provision selected devices
                return await self._provision_devices(selected_macs)

        # Build device options
        device_options = []
        for device in self._cloud_devices:
            mac = device.get("mac", "")
            product = device.get("product", {})
            name = product.get("en_name", "Air Monitor Lite")
            status = device.get("_status", "unknown")
            private_config = device.get("privateConfig", {})
            config_name = private_config.get("name", "")
            
            # Check if already configured in HA
            existing = self._async_current_ids()
            is_configured = f"{DOMAIN}_{mac}" in existing
            
            if is_configured:
                label = f"✅ {name} ({_format_mac(mac)}) - Already in HA"
            elif status == "bound":
                label = f"🔗 {name} ({_format_mac(mac)}) - Config: {config_name} (will rebind)"
            else:
                label = f"🆕 {name} ({_format_mac(mac)}) - New device"
            
            device_options.append(
                selector.SelectOptionDict(value=mac, label=label)
            )

        return self.async_show_form(
            step_id="select_devices",
            data_schema=vol.Schema({
                vol.Required("devices"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=device_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }),
            errors=errors,
            description_placeholders={
                "count": str(len(self._cloud_devices)),
            }
        )

    async def _provision_devices(self, macs: list[str]) -> FlowResult:
        """Provision selected devices with MQTT config."""
        if not self._developer_api:
            return self.async_abort(reason="not_logged_in")

        # Use selected config or create new one
        if self._selected_config_id:
            config_id = self._selected_config_id
            _LOGGER.info("Using pre-selected config ID: %s", config_id)
        else:
            # Create new MQTT config
            config_id = await self._developer_api.create_mqtt_config(
                name="Home Assistant Auto-Config",
                mqtt_host=self._mqtt_config.get(CONF_MQTT_HOST, ""),
                mqtt_port=int(self._mqtt_config.get(CONF_MQTT_PORT, 1883)),
                mqtt_username=self._mqtt_config.get(CONF_MQTT_USERNAME, ""),
                mqtt_password=self._mqtt_config.get(CONF_MQTT_PASSWORD, ""),
            )

        if not config_id:
            return self.async_abort(reason="config_creation_failed")

        # Process each device
        for mac in macs:
            device = next((d for d in self._cloud_devices if d.get("mac") == mac), None)
            if device:
                status = device.get("_status")
                if status == "unbound":
                    # New device - just bind
                    await self._developer_api.bind_device_to_config(mac, config_id)
                    _LOGGER.info("Provisioned new device %s with config %d", mac, config_id)
                elif status == "bound":
                    # Already bound - rebind to force config resend
                    await self._developer_api.rebind_device(mac, config_id)
                    _LOGGER.info("Re-provisioned device %s with config %d", mac, config_id)

        # Close API
        await self._developer_api.close()

        # Create entry for first device
        first_mac = macs[0]
        await self.async_set_unique_id(f"{DOMAIN}_{first_mac}")
        self._abort_if_unique_id_configured()
        
        data = {
            CONF_MAC: first_mac,
            CONF_STATE_TOPIC: STATE_TOPIC_TEMPLATE.format(mac=first_mac),
            CONF_AVAIL_TOPIC: AVAIL_TOPIC_TEMPLATE.format(mac=first_mac),
            CONF_QINGPING_EMAIL: self._qingping_credentials.get(CONF_QINGPING_EMAIL),
            CONF_QINGPING_PASSWORD: self._qingping_credentials.get(CONF_QINGPING_PASSWORD),
            **self._mqtt_config,
        }
        
        title = f"Qingping Air Monitor ({_format_mac(first_mac)})"
        if len(macs) > 1:
            title += f" +{len(macs)-1} more"
        
        return self.async_create_entry(title=title, data=data)

    # =========================================================================
    # MQTT SCAN FLOW
    # =========================================================================

    async def async_step_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Scan MQTT for devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input.get("device")
            if selected and selected in self._discovered_devices:
                device = self._discovered_devices[selected]
                mac = device["mac"]
                await self.async_set_unique_id(f"{DOMAIN}_{mac}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Qingping Air Monitor ({_format_mac(mac)})",
                    data={
                        CONF_MAC: mac,
                        CONF_STATE_TOPIC: STATE_TOPIC_TEMPLATE.format(mac=mac),
                        CONF_AVAIL_TOPIC: AVAIL_TOPIC_TEMPLATE.format(mac=mac),
                    },
                )
            elif user_input.get("action") == "rescan":
                self._discovered_devices = {}
                return await self.async_step_discovery()
            elif user_input.get("action") == "manual":
                return await self.async_step_manual()
            else:
                errors["base"] = "no_device_selected"
        else:
            self._discovered_devices = {}
            await self._scan_for_devices()

        if not self._discovered_devices:
            return self.async_show_form(
                step_id="discovery",
                data_schema=vol.Schema({
                    vol.Required("action", default="rescan"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="rescan", label="🔄 Scan again"),
                                selector.SelectOptionDict(value="manual", label="✏️ Enter MAC manually"),
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }),
                errors={"base": "no_devices_found"},
            )

        device_options = {
            mac: f"Qingping Air Monitor ({_format_mac(mac)})"
            for mac, info in self._discovered_devices.items()
        }

        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema({
                vol.Required("device"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=k, label=v)
                            for k, v in device_options.items()
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }),
            errors=errors,
        )

    async def _scan_for_devices(self) -> None:
        """Scan MQTT for devices."""
        found: dict[str, dict[str, Any]] = {}

        def on_message(msg) -> None:
            try:
                mac = None
                parts = msg.topic.split("/")
                
                if len(parts) >= 2 and parts[0].lower() == "qingping":
                    potential_mac = _norm_mac(parts[1])
                    if MAC_RE.match(potential_mac):
                        mac = potential_mac

                if mac:
                    existing = self._async_current_ids()
                    if f"{DOMAIN}_{mac}" not in existing:
                        found[mac] = {"mac": mac}
                        _LOGGER.info("Discovery: Found device %s", mac)
            except Exception as e:
                _LOGGER.debug("Discovery error: %s", e)

        try:
            unsub = await mqtt.async_subscribe(self.hass, "qingping/#", on_message, qos=0)
            _LOGGER.info("Discovery: Scanning for 10 seconds...")
            await asyncio.sleep(10)
            unsub()
        except Exception as e:
            _LOGGER.error("Discovery failed: %s", e)

        self._discovered_devices = found

    # =========================================================================
    # MANUAL ENTRY FLOW
    # =========================================================================

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manual MAC entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = _norm_mac(user_input.get(CONF_MAC, ""))
            if not MAC_RE.match(mac):
                errors[CONF_MAC] = "invalid_mac"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{mac}")
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=f"Qingping Air Monitor ({_format_mac(mac)})",
                    data={
                        CONF_MAC: mac,
                        CONF_STATE_TOPIC: STATE_TOPIC_TEMPLATE.format(mac=mac),
                        CONF_AVAIL_TOPIC: AVAIL_TOPIC_TEMPLATE.format(mac=mac),
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_MAC): selector.TextSelector(),
            }),
            errors=errors,
            description_placeholders={"example": "AABBCCDDEEFF"},
        )

    # =========================================================================
    # OPTIONS FLOW
    # =========================================================================

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.config_entry.data
        options = self.config_entry.options
        mac = data.get(CONF_MAC, "")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_STATE_TOPIC,
                    default=options.get(CONF_STATE_TOPIC, STATE_TOPIC_TEMPLATE.format(mac=mac))
                ): str,
                vol.Required(
                    CONF_AVAIL_TOPIC,
                    default=options.get(CONF_AVAIL_TOPIC, AVAIL_TOPIC_TEMPLATE.format(mac=mac))
                ): str,
                vol.Optional(
                    CONF_API_APP_KEY,
                    default=options.get(CONF_API_APP_KEY, data.get(CONF_API_APP_KEY, ""))
                ): str,
                vol.Optional(
                    CONF_API_APP_SECRET,
                    default=options.get(CONF_API_APP_SECRET, data.get(CONF_API_APP_SECRET, ""))
                ): str,
            }),
        )
