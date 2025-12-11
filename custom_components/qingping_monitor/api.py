"""Qingping Cloud API client for device management."""
from __future__ import annotations

import logging
import base64
import aiohttp
from typing import Any

from .const import QINGPING_OAUTH_URL, QINGPING_API_URL

_LOGGER = logging.getLogger(__name__)


class QingpingApiClient:
    """Client for Qingping Cloud API."""

    def __init__(self, app_key: str, app_secret: str) -> None:
        """Initialize the API client."""
        self._app_key = app_key
        self._app_secret = app_secret
        self._access_token: str | None = None
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def authenticate(self) -> bool:
        """Get OAuth access token."""
        try:
            session = await self._get_session()
            
            # Create Basic Auth header
            credentials = f"{self._app_key}:{self._app_secret}"
            encoded = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            data = {
                "grant_type": "client_credentials",
                "scope": "device_full_access",
            }
            
            async with session.post(QINGPING_OAUTH_URL, headers=headers, data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self._access_token = result.get("access_token")
                    _LOGGER.info("Qingping API: Authentication successful")
                    return True
                else:
                    _LOGGER.error("Qingping API: Authentication failed - %s", resp.status)
                    return False
                    
        except Exception as e:
            _LOGGER.error("Qingping API: Authentication error - %s", e)
            return False

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get list of devices from cloud."""
        if not self._access_token:
            if not await self.authenticate():
                return []
        
        try:
            session = await self._get_session()
            headers = {"Authorization": f"Bearer {self._access_token}"}
            
            import time
            url = f"{QINGPING_API_URL}/devices?timestamp={int(time.time() * 1000)}"
            
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    devices = result.get("devices", [])
                    _LOGGER.info("Qingping API: Found %d devices", len(devices))
                    return devices
                elif resp.status == 401:
                    # Token expired, re-authenticate
                    _LOGGER.info("Qingping API: Token expired, re-authenticating...")
                    self._access_token = None
                    if await self.authenticate():
                        return await self.get_devices()
                    return []
                else:
                    _LOGGER.error("Qingping API: Get devices failed - %s", resp.status)
                    return []
                    
        except Exception as e:
            _LOGGER.error("Qingping API: Get devices error - %s", e)
            return []

    async def get_device_data(self, mac: str) -> dict[str, Any] | None:
        """Get current data for a specific device."""
        devices = await self.get_devices()
        
        mac_normalized = mac.upper().replace(":", "")
        
        for device in devices:
            device_mac = device.get("info", {}).get("mac", "").upper().replace(":", "")
            if device_mac == mac_normalized:
                return device.get("data", {})
        
        _LOGGER.warning("Qingping API: Device %s not found in cloud", mac)
        return None

    async def update_device_settings(self, mac: str, settings: dict[str, Any]) -> bool:
        """Update device settings via cloud API."""
        if not self._access_token:
            if not await self.authenticate():
                return False
        
        try:
            session = await self._get_session()
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }
            
            mac_normalized = mac.upper().replace(":", "")
            url = f"{QINGPING_API_URL}/devices/settings"
            
            payload = {
                "mac": [mac_normalized],
                "settings": settings,
            }
            
            async with session.put(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    _LOGGER.info("Qingping API: Settings updated for %s", mac)
                    return True
                else:
                    body = await resp.text()
                    _LOGGER.error("Qingping API: Update settings failed - %s: %s", resp.status, body)
                    return False
                    
        except Exception as e:
            _LOGGER.error("Qingping API: Update settings error - %s", e)
            return False

    async def trigger_device_sync(self, mac: str) -> bool:
        """
        Trigger device to re-sync with cloud.
        
        This can help when device stops sending MQTT data.
        The cloud will push new config to device on next check-in.
        """
        _LOGGER.info("Qingping API: Triggering sync for %s", mac)
        
        # Update a harmless setting to trigger device sync
        # This causes the cloud to push config to device
        return await self.update_device_settings(mac, {
            "report_interval": 60,  # Default value
        })
