"""Watchdog for monitoring Qingping device connectivity."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Callable, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.persistent_notification import async_create, async_dismiss

from .const import (
    DOMAIN,
    WATCHDOG_CHECK_INTERVAL,
    WATCHDOG_WARNING_THRESHOLD,
    WATCHDOG_CRITICAL_THRESHOLD,
    WATCHDOG_KEEPALIVE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class QingpingWatchdog:
    """Watchdog to monitor device connectivity and send keepalives."""

    def __init__(
        self,
        hass: HomeAssistant,
        mac: str,
        send_keepalive: Callable[[], Any],
        on_warning: Callable[[int], Any] | None = None,
        on_critical: Callable[[int], Any] | None = None,
    ) -> None:
        """Initialize the watchdog."""
        self._hass = hass
        self._mac = mac
        self._formatted_mac = ":".join(mac[i:i+2] for i in range(0, 12, 2))
        self._send_keepalive = send_keepalive
        self._on_warning = on_warning
        self._on_critical = on_critical
        
        self._last_data_received: datetime | None = None
        self._last_keepalive_sent: datetime | None = None
        self._warning_sent = False
        self._critical_sent = False
        self._unsub_interval = None
        self._notification_id = f"{DOMAIN}_{mac}_offline"

    def start(self) -> None:
        """Start the watchdog."""
        self._unsub_interval = async_track_time_interval(
            self._hass,
            self._check_connection,
            timedelta(seconds=WATCHDOG_CHECK_INTERVAL),
        )
        _LOGGER.info("Watchdog started for %s (check every %ds)", self._mac, WATCHDOG_CHECK_INTERVAL)

    def stop(self) -> None:
        """Stop the watchdog."""
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
        _LOGGER.info("Watchdog stopped for %s", self._mac)

    @callback
    def mark_data_received(self) -> None:
        """Mark that data was received from device."""
        self._last_data_received = datetime.now(timezone.utc)
        
        # Clear warnings if we were offline
        if self._warning_sent or self._critical_sent:
            _LOGGER.info("Device %s is back online!", self._mac)
            self._dismiss_notification()
            self._warning_sent = False
            self._critical_sent = False

    def _get_seconds_since_last_data(self) -> int:
        """Get seconds since last data received."""
        if self._last_data_received is None:
            return 0  # No data yet, don't trigger warnings
        
        delta = datetime.now(timezone.utc) - self._last_data_received
        return int(delta.total_seconds())

    @callback
    def _check_connection(self, _now=None) -> None:
        """Check device connection status."""
        seconds_offline = self._get_seconds_since_last_data()
        
        if seconds_offline == 0:
            # No data received yet, skip check
            return
        
        _LOGGER.debug(
            "Watchdog %s: %d seconds since last data (warn=%d, crit=%d)",
            self._mac, seconds_offline, WATCHDOG_WARNING_THRESHOLD, WATCHDOG_CRITICAL_THRESHOLD
        )
        
        # Send keepalive if needed
        if self._should_send_keepalive():
            self._send_keepalive_now()
        
        # Check thresholds
        if seconds_offline >= WATCHDOG_CRITICAL_THRESHOLD:
            if not self._critical_sent:
                self._handle_critical(seconds_offline)
        elif seconds_offline >= WATCHDOG_WARNING_THRESHOLD:
            if not self._warning_sent:
                self._handle_warning(seconds_offline)

    def _should_send_keepalive(self) -> bool:
        """Check if we should send a keepalive."""
        if self._last_keepalive_sent is None:
            return True
        
        delta = datetime.now(timezone.utc) - self._last_keepalive_sent
        return delta.total_seconds() >= WATCHDOG_KEEPALIVE_INTERVAL

    def _send_keepalive_now(self) -> None:
        """Send keepalive to device."""
        _LOGGER.debug("Watchdog %s: Sending keepalive", self._mac)
        try:
            self._send_keepalive()
            self._last_keepalive_sent = datetime.now(timezone.utc)
        except Exception as e:
            _LOGGER.error("Watchdog %s: Failed to send keepalive: %s", self._mac, e)

    def _handle_warning(self, seconds_offline: int) -> None:
        """Handle warning threshold reached."""
        minutes = seconds_offline // 60
        _LOGGER.warning(
            "Qingping device %s has not sent data for %d minutes!",
            self._mac, minutes
        )
        
        self._warning_sent = True
        
        # Create notification
        async_create(
            self._hass,
            f"⚠️ Qingping Air Monitor ({self._formatted_mac}) has not sent data for {minutes} minutes. "
            f"The integration is attempting to reconnect.",
            title="Qingping Device Warning",
            notification_id=self._notification_id,
        )
        
        # Try to wake up device
        self._send_keepalive_now()
        
        if self._on_warning:
            self._on_warning(seconds_offline)

    def _handle_critical(self, seconds_offline: int) -> None:
        """Handle critical threshold reached."""
        minutes = seconds_offline // 60
        _LOGGER.error(
            "CRITICAL: Qingping device %s has been offline for %d minutes!",
            self._mac, minutes
        )
        
        self._critical_sent = True
        
        # Update notification to critical
        async_create(
            self._hass,
            f"🔴 **CRITICAL:** Qingping Air Monitor ({self._formatted_mac}) has been offline for {minutes} minutes!\n\n"
            f"**Possible solutions:**\n"
            f"1. Power cycle the device (turn off and on)\n"
            f"2. Check if device is connected to WiFi\n"
            f"3. Re-bind device at developer.qingping.co\n"
            f"4. Check MQTT broker connectivity",
            title="Qingping Device OFFLINE",
            notification_id=self._notification_id,
        )
        
        if self._on_critical:
            self._on_critical(seconds_offline)

    def _dismiss_notification(self) -> None:
        """Dismiss the offline notification."""
        async_dismiss(self._hass, self._notification_id)
