"""Sensor platform for Qingping Monitor integration."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    CONF_MAC,
    CONF_STATE_TOPIC,
    CONF_AVAIL_TOPIC,
    CONF_UPDATE_INTERVAL,
    STATE_TOPIC_TEMPLATE,
    DOWN_TOPIC_TEMPLATE,
    AVAIL_TOPIC_TEMPLATE,
    DEFAULT_INTERVAL_SECONDS,
    SETTING_REPORT_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# Units
CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = "µg/m³"


@dataclass
class QingpingShared:
    """Shared state between all entities of one device."""

    mac: str
    device_info: DeviceInfo
    last_payload: dict[str, Any] = field(default_factory=dict)
    last_type12: dict[str, Any] = field(default_factory=dict)  # Sensor data
    last_type13: dict[str, Any] = field(default_factory=dict)  # Network/status data
    available: bool = False


def _safe_json(payload: bytes | str) -> dict[str, Any] | None:
    """Safely parse JSON payload."""
    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return json.loads(payload)
    except Exception as e:
        _LOGGER.debug("Could not parse JSON payload: %s (%s)", payload[:100] if payload else "", e)
        return None


def _last_sensor_block(data: dict[str, Any]) -> dict[str, Any]:
    """Get the last sensor data block from payload."""
    sensor_data = data.get("sensorData")
    if isinstance(sensor_data, list) and sensor_data:
        return sensor_data[-1] or {}

    if any(k in data for k in ["temperature", "humidity", "co2", "pm25", "pm10", "battery"]):
        return data

    return {}


def _get_nested_value(block: dict[str, Any], key: str) -> float | None:
    """Extract value from nested structure or flat structure."""
    try:
        nested = block.get(key)
        if isinstance(nested, dict):
            v = nested.get("value")
            if v is not None:
                return float(v)

        flat = block.get(key)
        if flat is not None and not isinstance(flat, dict):
            return float(flat)

        return None
    except (ValueError, TypeError):
        return None


# ============================================================================
# WiFi Info Parsing - Format: "SSID,RSSI,Channel,BSSID"
# Example: "MyWiFi,-49,3,AA:BB:CC:DD:EE:FF"
# ============================================================================

def _parse_wifi_info(data: dict[str, Any]) -> dict[str, Any]:
    """Parse wifi_info string into components."""
    result = {
        "ssid": None,
        "rssi": None,
        "channel": None,
        "bssid": None,
    }
    
    info = data.get("wifi_info")
    if not info or not isinstance(info, str):
        return result
    
    parts = info.split(",")
    
    if len(parts) >= 1 and parts[0]:
        result["ssid"] = parts[0]
    
    if len(parts) >= 2:
        try:
            result["rssi"] = int(parts[1])
        except (ValueError, TypeError):
            pass
    
    if len(parts) >= 3:
        try:
            result["channel"] = int(parts[2])
        except (ValueError, TypeError):
            pass
    
    if len(parts) >= 4 and parts[3]:
        result["bssid"] = parts[3].upper()
    
    return result


def _wifi_rssi_from_wifi_info(data: dict[str, Any]) -> int | None:
    """Extract WiFi RSSI from wifi_info string or rssi field."""
    rssi = data.get("rssi") or data.get("wifi_rssi")
    if rssi is not None:
        try:
            return int(rssi)
        except (ValueError, TypeError):
            pass

    return _parse_wifi_info(data).get("rssi")


# ============================================================================
# Base Sensor Class
# ============================================================================

class _BaseQingpingSensor(SensorEntity):
    """Base class for Qingping sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, shared: QingpingShared, name: str, key: str) -> None:
        """Initialize the sensor."""
        self.shared = shared
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"qingping_{shared.mac}_{key}"
        self._attr_device_info = shared.device_info
        self._state: Any = None

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.shared.available or self._state is not None

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        """Update state from payload. Override in subclasses."""

    @callback
    def handle_mqtt(self, data: dict[str, Any]) -> None:
        """Handle MQTT message."""
        old_state = self._state
        self._update_from_payload(data)
        if self._state != old_state:
            _LOGGER.debug("%s: %s -> %s", self._attr_name, old_state, self._state)
        self.async_write_ha_state()


# ============================================================================
# Environmental Sensors (Type 12)
# ============================================================================

class TemperatureSensor(_BaseQingpingSensor):
    """Temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Temperature", "temperature")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        block = _last_sensor_block(data)
        val = _get_nested_value(block, "temperature")
        if val is not None:
            self._state = val


class HumiditySensor(_BaseQingpingSensor):
    """Humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Humidity", "humidity")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        block = _last_sensor_block(data)
        val = _get_nested_value(block, "humidity")
        if val is not None:
            self._state = val


class CO2Sensor(_BaseQingpingSensor):
    """CO2 sensor."""

    _attr_device_class = SensorDeviceClass.CO2
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "CO2", "co2")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        block = _last_sensor_block(data)
        val = _get_nested_value(block, "co2")
        if val is not None:
            self._state = val


class PM25Sensor(_BaseQingpingSensor):
    """PM2.5 sensor."""

    _attr_device_class = SensorDeviceClass.PM25
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "PM2.5", "pm25")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        block = _last_sensor_block(data)
        val = _get_nested_value(block, "pm25")
        if val is not None:
            self._state = val


class PM10Sensor(_BaseQingpingSensor):
    """PM10 sensor."""

    _attr_device_class = SensorDeviceClass.PM10
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "PM10", "pm10")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        block = _last_sensor_block(data)
        val = _get_nested_value(block, "pm10")
        if val is not None:
            self._state = val


class BatterySensor(_BaseQingpingSensor):
    """Battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Battery", "battery")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        block = _last_sensor_block(data)
        val = _get_nested_value(block, "battery")
        if val is not None:
            self._state = val


class TVOCSensor(_BaseQingpingSensor):
    """TVOC sensor (if available)."""

    _attr_device_class = SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "TVOC", "tvoc")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        block = _last_sensor_block(data)
        val = _get_nested_value(block, "tvoc")
        if val is not None:
            self._state = val


# ============================================================================
# Network & Device Info Sensors (Type 13)
# ============================================================================

class WifiRssiSensor(_BaseQingpingSensor):
    """WiFi RSSI sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_icon = "mdi:wifi"

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "WiFi Signal", "wifi_rssi")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        val = _wifi_rssi_from_wifi_info(data)
        if val is not None:
            self._state = val


class WifiSsidSensor(_BaseQingpingSensor):
    """WiFi SSID sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _attr_icon = "mdi:wifi"

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "WiFi SSID", "wifi_ssid")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        wifi = _parse_wifi_info(data)
        if wifi["ssid"]:
            self._state = wifi["ssid"]


class WifiChannelSensor(_BaseQingpingSensor):
    """WiFi Channel sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _attr_icon = "mdi:wifi-settings"

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "WiFi Channel", "wifi_channel")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        wifi = _parse_wifi_info(data)
        if wifi["channel"] is not None:
            self._state = wifi["channel"]


class WifiBssidSensor(_BaseQingpingSensor):
    """WiFi BSSID (Access Point MAC) sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _attr_icon = "mdi:router-wireless"

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "WiFi BSSID", "wifi_bssid")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        wifi = _parse_wifi_info(data)
        if wifi["bssid"]:
            self._state = wifi["bssid"]


class WifiMacSensor(_BaseQingpingSensor):
    """Device WiFi MAC address sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _attr_icon = "mdi:network"

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "WiFi MAC", "wifi_mac")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        mac = data.get("wifi_mac") or data.get("mac")
        if mac:
            # Format as XX:XX:XX:XX:XX:XX
            mac = mac.upper().replace(":", "").replace("-", "")
            if len(mac) == 12:
                self._state = ":".join(mac[i:i+2] for i in range(0, 12, 2))
            else:
                self._state = mac


class FirmwareSensor(_BaseQingpingSensor):
    """Firmware/Software version sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _attr_icon = "mdi:tag"

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Firmware", "firmware")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        val = data.get("sw_version") or data.get("version") or data.get("firmware")
        if val:
            self._state = str(val)


class ModuleVersionSensor(_BaseQingpingSensor):
    """Module version sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _attr_icon = "mdi:chip"

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Module Version", "module_version")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        val = data.get("module_version")
        if val:
            self._state = str(val)


class HardwareVersionSensor(_BaseQingpingSensor):
    """Hardware version sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _attr_icon = "mdi:memory"

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Hardware Version", "hw_version")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        val = data.get("hw_version")
        if val:
            self._state = str(val)


class IotPlatformSensor(_BaseQingpingSensor):
    """IoT Platform sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _attr_icon = "mdi:cloud"

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "IoT Platform", "iot_platform")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        val = data.get("iot_platform")
        if val is not None:
            # Map known values
            platform_map = {
                0: "Local/None",
                1: "Qingping Cloud",
                2: "Apple HomeKit",
                3: "Mi Home",
            }
            self._state = platform_map.get(int(val), f"Unknown ({val})")


class TimezoneSensor(_BaseQingpingSensor):
    """Device timezone sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _attr_icon = "mdi:map-clock"

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Timezone", "timezone")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        val = data.get("timezone")
        if val is not None:
            # Timezone offset in hours
            offset = int(val)
            if offset >= 0:
                self._state = f"UTC+{offset}"
            else:
                self._state = f"UTC{offset}"


class MessageTypeSensor(_BaseQingpingSensor):
    """Last message type sensor (for debugging)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _attr_icon = "mdi:message-text"

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Message Type", "msg_type")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        msg_type = data.get("type")
        if msg_type is not None:
            # Convert to string for consistent lookup
            msg_type_str = str(msg_type)
            type_map = {
                "10": "Heartbeat",
                "12": "Sensor Data",
                "13": "Device Status",
                "17": "Sensor Data (Buffered)",
                "18": "Config ACK",
                "28": "Device Settings",
            }
            self._state = type_map.get(msg_type_str, f"Type {msg_type}")


class LastUpdateSensor(_BaseQingpingSensor):
    """Last update timestamp sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Last Update", "last_update")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        # Return datetime object, NOT string! HA handles formatting.
        self._state = datetime.now(timezone.utc)


# ============================================================================
# Binary Sensor
# ============================================================================

class AvailabilityBinary(BinarySensorEntity):
    """Availability binary sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, shared: QingpingShared) -> None:
        self.shared = shared
        self._attr_name = "Connectivity"
        self._attr_unique_id = f"qingping_{shared.mac}_availability"
        self._attr_device_info = shared.device_info
        self._last_seen: datetime | None = None

    @property
    def is_on(self) -> bool | None:
        """Return True if device is online."""
        # If we've seen any message, consider online
        if self._last_seen is not None:
            return True
        return self.shared.available

    @property
    def available(self) -> bool:
        """Entity is always available (shows state even without messages)."""
        return True

    @callback
    def handle_availability(self, payload: bytes | str) -> None:
        """Handle availability MQTT message."""
        try:
            val = payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)
        except Exception:
            val = str(payload)

        self.shared.available = val.strip().lower() in ("online", "true", "1", "on")
        self._last_seen = datetime.now(timezone.utc)
        self.async_write_ha_state()

    @callback
    def mark_online(self) -> None:
        """Mark device as online (called when any MQTT message received)."""
        self._last_seen = datetime.now(timezone.utc)
        self.shared.available = True
        self.async_write_ha_state()


# ============================================================================
# Setup
# ============================================================================

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Qingping sensors from a config entry."""
    mac = (entry.options.get(CONF_MAC) or entry.data.get(CONF_MAC) or "").upper()
    if not mac:
        _LOGGER.error("No MAC configured in entry")
        return

    state_topic = (
        entry.options.get(CONF_STATE_TOPIC)
        or entry.data.get(CONF_STATE_TOPIC)
        or STATE_TOPIC_TEMPLATE.format(mac=mac)
    )
    avail_topic = (
        entry.options.get(CONF_AVAIL_TOPIC)
        or entry.data.get(CONF_AVAIL_TOPIC)
        or AVAIL_TOPIC_TEMPLATE.format(mac=mac)
    )

    _LOGGER.info(
        "Setting up Qingping Monitor: MAC=%s, state_topic=%s, avail_topic=%s",
        mac, state_topic, avail_topic,
    )

    formatted_mac = ":".join(mac[i:i+2] for i in range(0, 12, 2))

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"qingping_{mac}")},
        name=f"Qingping Air Monitor ({formatted_mac})",
        manufacturer="Qingping",
        model="Air Monitor Lite",
    )

    # Initialize shared data storage for settings (used by number, switch, select entities)
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if mac not in hass.data[DOMAIN]:
        hass.data[DOMAIN][mac] = {}
    
    shared_settings = hass.data[DOMAIN][mac]

    shared = QingpingShared(
        mac=mac,
        device_info=device_info,
        last_payload={},
        available=False,
    )

    # Create all entities
    entities: list[SensorEntity | BinarySensorEntity] = [
        # Environmental sensors
        TemperatureSensor(shared),
        HumiditySensor(shared),
        CO2Sensor(shared),
        PM25Sensor(shared),
        PM10Sensor(shared),
        BatterySensor(shared),
        TVOCSensor(shared),
        # Network & Device info sensors
        WifiRssiSensor(shared),
        WifiSsidSensor(shared),
        WifiChannelSensor(shared),
        WifiBssidSensor(shared),
        WifiMacSensor(shared),
        FirmwareSensor(shared),
        ModuleVersionSensor(shared),
        HardwareVersionSensor(shared),
        IotPlatformSensor(shared),
        TimezoneSensor(shared),
        MessageTypeSensor(shared),
        LastUpdateSensor(shared),
        # Binary sensor
        AvailabilityBinary(shared),
    ]

    async_add_entities(entities)

    @callback
    def _on_state(msg: mqtt.ReceiveMessage) -> None:
        """Handle state MQTT message."""
        payload_str = msg.payload[:500] if msg.payload else ""
        if isinstance(payload_str, bytes):
            payload_str = payload_str.decode("utf-8", errors="replace")[:500]
        _LOGGER.debug("MQTT received on [%s]: %s", msg.topic, payload_str)

        data = _safe_json(msg.payload)
        if not data:
            _LOGGER.warning("Could not parse MQTT payload as JSON from topic %s", msg.topic)
            return

        msg_type = str(data.get("type", ""))
        
        # Log first message with more detail
        if not shared.available:
            _LOGGER.info("First message from device! Type=%s, Topic=%s", msg_type, msg.topic)

        # Store payloads by type
        shared.last_payload = data
        
        # Mark device as online on ANY message received
        shared.available = True
        for entity in entities:
            if isinstance(entity, AvailabilityBinary):
                entity.mark_online()
                break

        # Type 12 and 17 contain sensor data - update environmental sensors
        if msg_type in ("12", "17"):
            shared.last_type12 = data
            # Log sensor values for debugging
            block = data.get("sensorData", [{}])[-1] if data.get("sensorData") else {}
            temp = block.get("temperature", {}).get("value") if isinstance(block.get("temperature"), dict) else block.get("temperature")
            _LOGGER.info("Sensor data (type %s): temp=%s", msg_type, temp)
            
            # Update ALL entities with sensor data
            for entity in entities:
                if isinstance(entity, _BaseQingpingSensor):
                    entity.handle_mqtt(data)
                elif isinstance(entity, AvailabilityBinary):
                    entity.async_write_ha_state()
                    
        # Type 13 is device status - update network/device info sensors
        elif msg_type == "13":
            shared.last_type13 = data
            _LOGGER.debug("Device status received")
            
            # Update only network/device entities, not environmental sensors
            for entity in entities:
                if isinstance(entity, (WifiRssiSensor, WifiSsidSensor, WifiChannelSensor, 
                                       WifiBssidSensor, WifiMacSensor, FirmwareSensor,
                                       ModuleVersionSensor, HardwareVersionSensor,
                                       IotPlatformSensor, TimezoneSensor, MessageTypeSensor,
                                       LastUpdateSensor, AvailabilityBinary)):
                    entity.handle_mqtt(data) if isinstance(entity, _BaseQingpingSensor) else entity.async_write_ha_state()
                    
        # Type 10 is heartbeat - just update availability and timestamp
        elif msg_type == "10":
            _LOGGER.debug("Heartbeat received (type 10)")
            for entity in entities:
                if isinstance(entity, (MessageTypeSensor, LastUpdateSensor)):
                    entity.handle_mqtt(data)
                elif isinstance(entity, AvailabilityBinary):
                    entity.async_write_ha_state()
        
        # Type 18 is ACK response to our config commands
        elif msg_type == "18":
            ack_id = data.get("id", "?")
            result = data.get("result", "?")
            _LOGGER.info("Config ACK received: id=%s, result=%s", ack_id, result)
            # Update timestamp
            for entity in entities:
                if isinstance(entity, (MessageTypeSensor, LastUpdateSensor)):
                    entity.handle_mqtt(data)
        
        # Type 28 is device settings (all current settings from device)
        elif msg_type == "28":
            settings = data.get("setting", {})
            if settings:
                # Store ALL settings in shared data for config entities
                # This makes them available to Number/Switch/Select/Text entities
                shared_settings.update(settings)
                _LOGGER.info(
                    "Device settings received (Type 28): interval=%s, screensaver=%s, pm25_standard=%s",
                    settings.get("report_interval"),
                    settings.get("screensaver_type"),
                    settings.get("pm25_standard"),
                )
                _LOGGER.debug("Full Type 28 settings: %s", settings)
                
                # Fire event to notify config entities to refresh
                hass.bus.async_fire(f"{DOMAIN}_{mac}_settings_updated", settings)
                
            # Update timestamp
            for entity in entities:
                if isinstance(entity, (MessageTypeSensor, LastUpdateSensor)):
                    entity.handle_mqtt(data)
        
        # Unknown type - log and update timestamp only
        else:
            _LOGGER.warning("Unknown message type: %s (full payload: %s)", msg_type, str(data)[:200])

    @callback
    def _on_avail(msg: mqtt.ReceiveMessage) -> None:
        """Handle availability MQTT message."""
        _LOGGER.debug("Availability [%s]: %s", msg.topic, msg.payload)
        for entity in entities:
            if isinstance(entity, AvailabilityBinary):
                entity.handle_availability(msg.payload)

    # Subscribe
    _LOGGER.info("Subscribing to MQTT topics: state=%s, avail=%s", state_topic, avail_topic)
    unsub_state = await mqtt.async_subscribe(hass, state_topic, _on_state, qos=0)
    unsub_avail = await mqtt.async_subscribe(hass, avail_topic, _on_avail, qos=0)
    _LOGGER.info("MQTT subscriptions active - waiting for device data...")

    entry.async_on_unload(unsub_state)
    entry.async_on_unload(unsub_avail)

    # ========================================================================
    # Config Publishing - ONLY send report_interval to keep device sending data
    # Other settings are sent individually by Number/Switch/Select entities
    # ========================================================================
    down_topic = DOWN_TOPIC_TEMPLATE.format(mac=mac)
    config_id = [0]  # Mutable counter
    
    async def publish_config(_now=None) -> None:
        """Publish ONLY report_interval to device to keep it sending data."""
        # Read current interval from shared settings or entry options
        interval_seconds = (
            shared_settings.get(SETTING_REPORT_INTERVAL) or 
            entry.options.get(SETTING_REPORT_INTERVAL) or
            DEFAULT_INTERVAL_SECONDS
        )
        
        config_id[0] += 1
        # ONLY send interval settings - nothing else!
        config_payload = {
            "id": config_id[0],
            "need_ack": 1,
            "type": "17",
            "setting": {
                "report_interval": interval_seconds,
                "collect_interval": interval_seconds,
                "pm_sampling_interval": interval_seconds,
            }
        }
        try:
            await mqtt.async_publish(
                hass, down_topic, json.dumps(config_payload), qos=0, retain=False
            )
            _LOGGER.debug("Published interval config to %s (id=%d, interval=%d sec)", down_topic, config_id[0], interval_seconds)
        except Exception as e:
            _LOGGER.error("Failed to publish config: %s", e)

    # Send config immediately on startup to get data ASAP
    await publish_config()
    
    # Also send again after 3 seconds (in case MQTT wasn't fully ready)
    async def delayed_config(_now=None) -> None:
        await asyncio.sleep(3)
        await publish_config()
    
    hass.async_create_task(delayed_config())
    
    # Periodic config refresh every 5 minutes to keep device awake
    # (Individual settings are sent by Number/Switch/Select entities when changed)
    unsub_refresh = async_track_time_interval(hass, publish_config, timedelta(minutes=5))
    entry.async_on_unload(unsub_refresh)

    _LOGGER.info("Qingping Monitor ready: MAC=%s state='%s' down='%s'", mac, state_topic, down_topic)
