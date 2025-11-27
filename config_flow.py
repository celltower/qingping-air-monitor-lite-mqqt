"""Config flow for Qingping Monitor integration."""
from __future__ import annotations
import re
import logging
import asyncio
import json
import voluptuous as vol
from typing import Any

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_MAC,
    CONF_STATE_TOPIC,
    CONF_AVAIL_TOPIC,
    STATE_TOPIC_TEMPLATE,
    AVAIL_TOPIC_TEMPLATE,
    DISCOVERY_TOPIC,
)

_LOGGER = logging.getLogger(__name__)
MAC_RE = re.compile(r"^[0-9A-F]{12}$", re.I)


def _norm_mac(s: str) -> str:
    """Normalize MAC address to uppercase without separators."""
    s = s.strip().replace(":", "").replace("-", "").replace(".", "")
    return s.upper()


def _format_mac(mac: str) -> str:
    """Format MAC as XX:XX:XX:XX:XX:XX for display."""
    return ":".join(mac[i : i + 2] for i in range(0, 12, 2))


class QingpingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qingping Monitor."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, dict[str, Any]] = {}
        self._selected_mac: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - offer choice between scan and manual."""
        if user_input is not None:
            if user_input.get("method") == "scan":
                return await self.async_step_discovery()
            else:
                return await self.async_step_manual()
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("method", default="scan"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="scan", label="🔍 Auto-Scan for devices (recommended)"),
                            selector.SelectOptionDict(value="manual", label="✏️ Enter MAC address manually"),
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }),
        )

    async def async_step_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Scan for Qingping devices via MQTT."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # User selected a device
            selected = user_input.get("device")
            if selected and selected in self._discovered_devices:
                device = self._discovered_devices[selected]
                mac = device["mac"]

                await self.async_set_unique_id(f"{DOMAIN}_{mac}")
                self._abort_if_unique_id_configured()

                data = {
                    CONF_MAC: mac,
                    CONF_STATE_TOPIC: STATE_TOPIC_TEMPLATE.format(mac=mac),
                    CONF_AVAIL_TOPIC: AVAIL_TOPIC_TEMPLATE.format(mac=mac),
                }
                name = device.get("name", f"Qingping {_format_mac(mac)}")
                _LOGGER.info("Creating entry for %s with state_topic=%s", mac, data[CONF_STATE_TOPIC])
                return self.async_create_entry(title=name, data=data)
            elif user_input.get("action") == "rescan":
                # Rescan requested
                self._discovered_devices = {}
                return await self.async_step_discovery()
            elif user_input.get("action") == "manual":
                return await self.async_step_manual()
            else:
                errors["base"] = "no_device_selected"
        else:
            # First time - scan for devices
            self._discovered_devices = {}
            await self._scan_for_devices()

        if not self._discovered_devices:
            # No devices found - show options
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
                description_placeholders={"count": "0"},
                errors={"base": "no_devices_found"},
            )

        # Build selection list
        device_options = {
            mac: f"{info.get('name', 'Qingping')} ({_format_mac(mac)})"
            for mac, info in self._discovered_devices.items()
        }

        schema = vol.Schema(
            {
                vol.Required("device"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=k, label=v)
                            for k, v in device_options.items()
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="discovery",
            data_schema=schema,
            errors=errors,
            description_placeholders={"count": str(len(self._discovered_devices))},
        )

    async def _scan_for_devices(self) -> None:
        """Scan MQTT for Qingping devices."""
        found: dict[str, dict[str, Any]] = {}
        already_configured: list[str] = []
        message_count = [0]

        def on_message(msg: mqtt.ReceiveMessage) -> None:
            """Handle incoming MQTT message."""
            message_count[0] += 1
            _LOGGER.warning("DISCOVERY MSG #%d: topic=%s", message_count[0], msg.topic)
            
            try:
                # Parse payload
                payload_raw = msg.payload
                if isinstance(payload_raw, bytes):
                    payload_str = payload_raw.decode("utf-8", errors="replace")
                else:
                    payload_str = str(payload_raw)
                
                # Extract MAC from topic first (most reliable)
                mac = None
                parts = msg.topic.split("/")
                
                if len(parts) >= 2 and parts[0].lower() == "qingping":
                    potential_mac = _norm_mac(parts[1])
                    if MAC_RE.match(potential_mac):
                        mac = potential_mac
                        _LOGGER.warning("DISCOVERY MSG #%d: MAC from topic: %s", message_count[0], mac)

                # Parse JSON for fallback and device info
                data = {}
                try:
                    data = json.loads(payload_str) if payload_str else {}
                except:
                    pass
                
                # Fallback: try payload fields
                if not mac:
                    for field in ["mac", "wifi_mac", "device_mac"]:
                        if data.get(field):
                            potential = _norm_mac(str(data[field]))
                            if MAC_RE.match(potential):
                                mac = potential
                                _LOGGER.warning("DISCOVERY MSG #%d: MAC from field %s: %s", message_count[0], field, mac)
                                break

                if mac:
                    # Check if already configured
                    existing = self._async_current_ids()
                    unique_id = f"{DOMAIN}_{mac}"
                    
                    if unique_id in existing:
                        if mac not in already_configured:
                            already_configured.append(mac)
                            _LOGGER.warning("DISCOVERY MSG #%d: MAC %s already configured (skipping)", message_count[0], mac)
                    else:
                        msg_type = str(data.get("type", "?"))
                        found[mac] = {
                            "mac": mac,
                            "name": data.get("deviceName") or "Qingping Air Monitor",
                            "model": data.get("deviceModel", "Air Monitor Lite"),
                            "version": data.get("sw_version") or data.get("module_version") or "",
                            "type": msg_type,
                            "topic": msg.topic,
                        }
                        _LOGGER.warning("DISCOVERY MSG #%d: NEW device found MAC=%s", message_count[0], mac)
                else:
                    _LOGGER.warning("DISCOVERY MSG #%d: No valid MAC in message", message_count[0])
                    
            except Exception as e:
                _LOGGER.error("DISCOVERY MSG #%d: Exception: %s", message_count[0], e)

        # Subscribe to ALL qingping topics
        _LOGGER.warning("DISCOVERY: Starting scan...")
        
        # Use wildcard subscription
        try:
            unsub = await mqtt.async_subscribe(self.hass, "qingping/#", on_message, qos=0)
            _LOGGER.warning("DISCOVERY: Subscribed to qingping/#")
        except Exception as e:
            _LOGGER.error("DISCOVERY: Failed to subscribe: %s", e)
            self._discovered_devices = {}
            return

        # Wait 10 seconds for devices that send infrequently
        _LOGGER.warning("DISCOVERY: Waiting 10 seconds for messages...")
        await asyncio.sleep(10)

        # Unsubscribe
        try:
            unsub()
        except Exception:
            pass

        _LOGGER.warning("DISCOVERY: Complete. Messages: %d, New devices: %d, Already configured: %d", 
                       message_count[0], len(found), len(already_configured))
        
        if already_configured:
            _LOGGER.warning("DISCOVERY: Already configured MACs: %s", already_configured)
        
        for mac, info in found.items():
            _LOGGER.warning("DISCOVERY: New device available: %s", info)
        
        self._discovered_devices = found

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual MAC entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = _norm_mac(user_input.get(CONF_MAC, ""))
            if not MAC_RE.match(mac):
                errors[CONF_MAC] = "invalid_mac"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{mac}")
                self._abort_if_unique_id_configured()

                data = {
                    CONF_MAC: mac,
                    CONF_STATE_TOPIC: STATE_TOPIC_TEMPLATE.format(mac=mac),
                    CONF_AVAIL_TOPIC: AVAIL_TOPIC_TEMPLATE.format(mac=mac),
                }
                _LOGGER.info("Manual entry: MAC=%s, state_topic=%s", mac, data[CONF_STATE_TOPIC])
                return self.async_create_entry(
                    title=f"Qingping {_format_mac(mac)}", data=data
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_MAC): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }
        )

        return self.async_show_form(
            step_id="manual",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "example": "AABBCCDDEEFF or AA:BB:CC:DD:EE:FF"
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Qingping Monitor."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        data = self.config_entry.data
        options = self.config_entry.options

        mac = data.get(CONF_MAC, "")

        def _get(k: str, default: str) -> str:
            return options.get(k, data.get(k, default))

        default_state = _get(CONF_STATE_TOPIC, STATE_TOPIC_TEMPLATE.format(mac=mac))
        default_avail = _get(CONF_AVAIL_TOPIC, AVAIL_TOPIC_TEMPLATE.format(mac=mac))

        if user_input is not None:
            state_topic = user_input.get(CONF_STATE_TOPIC, default_state).strip()
            avail_topic = user_input.get(CONF_AVAIL_TOPIC, default_avail).strip()

            if not state_topic:
                errors[CONF_STATE_TOPIC] = "required"
            if not avail_topic:
                errors[CONF_AVAIL_TOPIC] = "required"

            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_STATE_TOPIC: state_topic,
                        CONF_AVAIL_TOPIC: avail_topic,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_STATE_TOPIC, default=default_state): str,
                vol.Required(CONF_AVAIL_TOPIC, default=default_avail): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
