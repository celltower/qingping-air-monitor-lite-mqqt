"""Sensor platform for Qingping Monitor."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    CONF_MAC,
    CONF_STATE_TOPIC,
    CONF_AVAIL_TOPIC,
    STATE_TOPIC_TEMPLATE,
    AVAIL_TOPIC_TEMPLATE,
    DOWN_TOPIC_TEMPLATE,
    DEFAULT_INTERVAL_SECONDS,
    SETTING_REPORT_INTERVAL,
    SETTING_COLLECT_INTERVAL,
    SETTING_PM_SAMPLING,
    WATCHDOG_KEEPALIVE_INTERVAL,
)
from .watchdog import QingpingWatchdog

_LOGGER = logging.getLogger(__name__)


def _safe_json(payload) -> dict | None:
    """Safely parse JSON payload."""
    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


@dataclass
class QingpingShared:
    """Shared state between sensors."""
    mac: str
    device_info: DeviceInfo
    available: bool = False
    last_payload: dict | None = None


# ============================================================================
# Base Sensor
# ============================================================================

class _BaseQingpingSensor(SensorEntity):
    """Base class for Qingping sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, shared: QingpingShared, name: str, key: str) -> None:
        """Initialize the sensor."""
        self.shared = shared
        self._attr_name = name
        self._attr_unique_id = f"qingping_{shared.mac}_{key}"
        self._attr_device_info = shared.device_info
        self._state: Any = None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.shared.available

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self._state

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        """Update state from MQTT payload. Override in subclasses."""
        pass

    @callback
    def handle_mqtt(self, data: dict[str, Any]) -> None:
        """Handle MQTT message."""
        old = self._state
        self._update_from_payload(data)
        if self._state != old:
            _LOGGER.debug("%s: %s -> %s", self._attr_name, old, self._state)
        self.async_write_ha_state()


# ============================================================================
# Environmental Sensors
# ============================================================================

class TemperatureSensor(_BaseQingpingSensor):
    """Temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Temperature", "temperature")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        sensor_data = data.get("sensorData", [{}])[0]
        temp = sensor_data.get("temperature", {})
        if "value" in temp:
            self._state = round(float(temp["value"]), 2)


class HumiditySensor(_BaseQingpingSensor):
    """Humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Humidity", "humidity")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        sensor_data = data.get("sensorData", [{}])[0]
        humi = sensor_data.get("humidity", {})
        if "value" in humi:
            self._state = round(float(humi["value"]), 2)


class CO2Sensor(_BaseQingpingSensor):
    """CO2 sensor."""

    _attr_device_class = SensorDeviceClass.CO2
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "CO2", "co2")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        sensor_data = data.get("sensorData", [{}])[0]
        co2 = sensor_data.get("co2", {})
        if "value" in co2:
            self._state = float(co2["value"])


class PM25Sensor(_BaseQingpingSensor):
    """PM2.5 sensor."""

    _attr_device_class = SensorDeviceClass.PM25
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "PM2.5", "pm25")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        sensor_data = data.get("sensorData", [{}])[0]
        pm25 = sensor_data.get("pm25", {})
        if "value" in pm25:
            self._state = float(pm25["value"])


class PM10Sensor(_BaseQingpingSensor):
    """PM10 sensor."""

    _attr_device_class = SensorDeviceClass.PM10
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "PM10", "pm10")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        sensor_data = data.get("sensorData", [{}])[0]
        pm10 = sensor_data.get("pm10", {})
        if "value" in pm10:
            self._state = float(pm10["value"])


class BatterySensor(_BaseQingpingSensor):
    """Battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Battery", "battery")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        sensor_data = data.get("sensorData", [{}])[0]
        battery = sensor_data.get("battery", {})
        if "value" in battery:
            self._state = int(battery["value"])


# ============================================================================
# Diagnostic Sensors
# ============================================================================

class WiFiSignalSensor(_BaseQingpingSensor):
    """WiFi signal strength sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "WiFi Signal", "wifi_rssi")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        wifi_info = data.get("wifi_info", "")
        if wifi_info and "," in wifi_info:
            parts = wifi_info.split(",")
            if len(parts) >= 2:
                try:
                    self._state = int(parts[1])
                except ValueError:
                    pass


class WiFiSsidSensor(_BaseQingpingSensor):
    """WiFi SSID sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:wifi"
    _attr_entity_registry_enabled_default = False

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "WiFi SSID", "wifi_ssid")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        wifi_info = data.get("wifi_info", "")
        if wifi_info and "," in wifi_info:
            self._state = wifi_info.split(",")[0]


class FirmwareSensor(_BaseQingpingSensor):
    """Firmware version sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:information-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Firmware", "firmware")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        version = data.get("sw_version") or data.get("module_version")
        if version:
            self._state = version


class MessageTypeSensor(_BaseQingpingSensor):
    """Message type sensor for debugging."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _attr_icon = "mdi:message-text"
    _attr_entity_registry_enabled_default = False

    def __init__(self, shared: QingpingShared) -> None:
        super().__init__(shared, "Message Type", "msg_type")

    def _update_from_payload(self, data: dict[str, Any]) -> None:
        msg_type = data.get("type")
        if msg_type is not None:
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
        # Return datetime object, NOT string!
        self._state = datetime.now(timezone.utc)


# ============================================================================
# Binary Sensor
# ============================================================================

class AvailabilityBinary(BinarySensorEntity):
    """Availability binary sensor."""

    _attr_has_entity_name = True
    _attr_name = "Availability"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, shared: QingpingShared) -> None:
        """Initialize the sensor."""
        self.shared = shared
        self._attr_unique_id = f"qingping_{shared.mac}_availability"
        self._attr_device_info = shared.device_info
        self._last_seen: datetime | None = None

    @property
    def is_on(self) -> bool | None:
        """Return True if device is online."""
        if self._last_seen is not None:
            return True
        return self.shared.available

    @property
    def available(self) -> bool:
        """Return True - sensor is always available."""
        return True

    @callback
    def handle_availability(self, payload) -> None:
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

    shared = QingpingShared(mac=mac, device_info=device_info)
    
    # Shared settings storage (populated by Type 28 messages)
    shared_settings: dict[str, Any] = {}
    hass.data[DOMAIN][entry.entry_id]["shared_settings"] = shared_settings
    hass.data[DOMAIN][entry.entry_id]["shared"] = shared

    # Create entities
    entities = [
        TemperatureSensor(shared),
        HumiditySensor(shared),
        CO2Sensor(shared),
        PM25Sensor(shared),
        PM10Sensor(shared),
        BatterySensor(shared),
        WiFiSignalSensor(shared),
        WiFiSsidSensor(shared),
        FirmwareSensor(shared),
        MessageTypeSensor(shared),
        LastUpdateSensor(shared),
        AvailabilityBinary(shared),
    ]

    async_add_entities(entities)

    # Type 18 ACK sender
    async def _send_ack(msg_id: int) -> None:
        """Send Type 18 ACK to device."""
        import time
        ack_payload = {
            "type": "18",
            "ack_id": msg_id,
            "code": 0,
            "timestamp": int(time.time()),
            "desc": ""
        }
        payload_str = json.dumps(ack_payload, separators=(",", ":"))
        await mqtt.async_publish(hass, down_topic, payload_str, qos=0, retain=False)
        _LOGGER.debug("Sent ACK for message %d to %s", msg_id, down_topic)

    # MQTT message handler
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
        
        # Log first message
        if not shared.available:
            _LOGGER.info("First message from device! Type=%s, Topic=%s", msg_type, msg.topic)

        # Mark device as online
        shared.available = True
        for entity in entities:
            if isinstance(entity, AvailabilityBinary):
                entity.mark_online()
                break

        # Notify watchdog
        if watchdog:
            watchdog.mark_data_received()

        # Type 12 and 17 contain sensor data
        if msg_type in ("12", "17"):
            sensor_data = data.get("sensorData", [{}])[0]
            _LOGGER.info("Sensor data (type %s): temp=%s", msg_type, sensor_data.get("temperature", {}).get("value"))
            for entity in entities:
                if isinstance(entity, _BaseQingpingSensor):
                    entity.handle_mqtt(data)
            
            # Send Type 18 ACK if device requested it (need_ack=1)
            if data.get("need_ack") == 1:
                msg_id = data.get("id")
                if msg_id:
                    hass.async_create_task(_send_ack(msg_id))

        # Type 13 contains device status
        elif msg_type == "13":
            _LOGGER.debug("Device status received")
            for entity in entities:
                if isinstance(entity, (WiFiSignalSensor, WiFiSsidSensor, FirmwareSensor)):
                    entity.handle_mqtt(data)
                elif isinstance(entity, (MessageTypeSensor, LastUpdateSensor)):
                    entity.handle_mqtt(data)

        # Type 28 contains device settings
        elif msg_type == "28":
            settings = data.get("setting", {})
            if settings:
                shared_settings.update(settings)
                _LOGGER.info("Device settings received (Type 28): interval=%s, screensaver=%s, pm25_standard=%s",
                            settings.get("report_interval"), settings.get("screensaver_type"), settings.get("pm25_standard"))
                _LOGGER.debug("Full Type 28 settings: %s", settings)
                # Fire event for config entities
                hass.bus.async_fire(f"{DOMAIN}_{mac}_settings_updated", settings)
            for entity in entities:
                if isinstance(entity, (MessageTypeSensor, LastUpdateSensor)):
                    entity.handle_mqtt(data)

        # Type 10 is heartbeat
        elif msg_type == "10":
            _LOGGER.debug("Heartbeat received")
            for entity in entities:
                if isinstance(entity, (MessageTypeSensor, LastUpdateSensor)):
                    entity.handle_mqtt(data)

        # Type 18 is config ACK
        elif msg_type == "18":
            _LOGGER.debug("Config ACK received")
            for entity in entities:
                if isinstance(entity, (MessageTypeSensor, LastUpdateSensor)):
                    entity.handle_mqtt(data)

        else:
            _LOGGER.warning("Unknown message type: %s", msg_type)

    @callback
    def _on_avail(msg: mqtt.ReceiveMessage) -> None:
        """Handle availability MQTT message."""
        _LOGGER.debug("Availability [%s]: %s", msg.topic, msg.payload)
        for entity in entities:
            if isinstance(entity, AvailabilityBinary):
                entity.handle_availability(msg.payload)

    # Subscribe to MQTT
    _LOGGER.info("Subscribing to MQTT topics: state=%s, avail=%s", state_topic, avail_topic)
    unsub_state = await mqtt.async_subscribe(hass, state_topic, _on_state, qos=0)
    unsub_avail = await mqtt.async_subscribe(hass, avail_topic, _on_avail, qos=0)
    _LOGGER.info("MQTT subscriptions active - waiting for device data...")

    entry.async_on_unload(unsub_state)
    entry.async_on_unload(unsub_avail)

    # ========================================================================
    # Config Publishing & Keepalive
    # ========================================================================
    down_topic = DOWN_TOPIC_TEMPLATE.format(mac=mac)
    config_id = [0]
    
    async def publish_config(_now=None) -> None:
        """Publish config to device (keepalive)."""
        interval_seconds = (
            shared_settings.get(SETTING_REPORT_INTERVAL) or 
            entry.options.get(SETTING_REPORT_INTERVAL) or
            DEFAULT_INTERVAL_SECONDS
        )
        
        config_id[0] += 1
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
        
        payload_str = json.dumps(config_payload, separators=(",", ":"))
        await mqtt.async_publish(hass, down_topic, payload_str, qos=0, retain=False)
        _LOGGER.debug("Published keepalive config to %s (id=%d, interval=%d sec)", 
                     down_topic, config_id[0], interval_seconds)

    # Initial config publish
    await publish_config()

    # Schedule periodic keepalive (every 5 minutes)
    unsub_keepalive = async_track_time_interval(
        hass,
        publish_config,
        timedelta(minutes=5),
    )
    entry.async_on_unload(unsub_keepalive)

    # ========================================================================
    # Watchdog
    # ========================================================================
    
    def send_keepalive():
        """Wrapper for watchdog keepalive."""
        hass.async_create_task(publish_config())
    
    # Get API client for critical callback
    api_client = hass.data[DOMAIN][entry.entry_id].get("api_client")
    
    async def on_critical(seconds_offline: int):
        """Handle critical offline event - try cloud rebind."""
        if api_client:
            _LOGGER.warning("Attempting cloud-based device sync for %s...", mac)
            success = await api_client.trigger_device_sync(mac)
            if success:
                _LOGGER.info("Cloud sync triggered for %s - device should reconnect soon", mac)
            else:
                _LOGGER.error("Cloud sync failed for %s", mac)
    
    watchdog = QingpingWatchdog(
        hass=hass,
        mac=mac,
        send_keepalive=send_keepalive,
        on_critical=lambda s: hass.async_create_task(on_critical(s)) if api_client else None,
    )
    watchdog.start()
    entry.async_on_unload(watchdog.stop)
    
    hass.data[DOMAIN][entry.entry_id]["watchdog"] = watchdog

    _LOGGER.info("Qingping Monitor ready: MAC=%s state='%s' down='%s' watchdog=active",
                mac, state_topic, down_topic)
