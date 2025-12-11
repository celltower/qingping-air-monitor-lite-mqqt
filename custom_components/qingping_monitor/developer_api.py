"""Qingping Developer Portal API for automatic device provisioning."""
from __future__ import annotations

import logging
import aiohttp
from typing import Any
from urllib.parse import quote

_LOGGER = logging.getLogger(__name__)

# API Endpoints
DEV_API_BASE = "https://developer.cleargrass.com"
DEV_LOGIN_URL = f"{DEV_API_BASE}/account/login"
DEV_CONFIG_URL = f"{DEV_API_BASE}/v1/private/config"
DEV_DEVICES_URL = f"{DEV_API_BASE}/v1/private/devices"

# Product codes
PRODUCT_AIR_MONITOR_LITE = "CGDN1"
PRODUCT_AIR_MONITOR = "CGS1"


class QingpingDeveloperApi:
    """Client for Qingping Developer Portal internal API."""

    def __init__(self) -> None:
        """Initialize the API client."""
        self._token: str | None = None
        self._user_id: int | None = None
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

    def _get_headers(self, with_auth: bool = True, json_content: bool = False) -> dict:
        """Get request headers."""
        headers = {
            "accept": "application/json, text/plain, */*",
            "language": "en-US",
            "origin": "https://developer.qingping.co",
            "referer": "https://developer.qingping.co/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if with_auth and self._token:
            headers["authorization"] = f"Bearer {self._token}"
        if json_content:
            headers["content-type"] = "application/json"
        else:
            headers["content-type"] = "application/x-www-form-urlencoded"
        return headers

    async def login(self, email: str, password: str) -> bool:
        """
        Login to Qingping Developer Portal.
        
        Args:
            email: Qingping account email
            password: Qingping account password
            
        Returns:
            True if login successful
        """
        try:
            session = await self._get_session()
            
            # URL-encode the credentials
            data = f"account={quote(email)}&password={quote(password)}&cid=&country_code=86"
            
            headers = self._get_headers(with_auth=False)
            
            async with session.post(DEV_LOGIN_URL, headers=headers, data=data) as resp:
                result = await resp.json()
                
                if result.get("code") == 0 and "data" in result:
                    self._token = result["data"]["token"]
                    self._user_id = result["data"].get("qing_user_id")
                    _LOGGER.info("Developer API: Login successful (user: %s)", 
                               result["data"].get("display_name"))
                    return True
                else:
                    _LOGGER.error("Developer API: Login failed - %s", result.get("msg", "Unknown error"))
                    return False
                    
        except Exception as e:
            _LOGGER.error("Developer API: Login error - %s", e)
            return False

    async def get_configs(self) -> list[dict[str, Any]]:
        """Get list of existing private configs."""
        if not self._token:
            _LOGGER.error("Developer API: Not logged in")
            return []
            
        try:
            session = await self._get_session()
            headers = self._get_headers()
            
            url = f"{DEV_CONFIG_URL}?limit=50&offset=0"
            
            async with session.get(url, headers=headers) as resp:
                result = await resp.json()
                
                if result.get("code") == 200:
                    configs = result.get("data", {}).get("configs", [])
                    _LOGGER.info("Developer API: Found %d configs", len(configs))
                    return configs
                else:
                    _LOGGER.error("Developer API: Get configs failed - %s", result.get("msg"))
                    return []
                    
        except Exception as e:
            _LOGGER.error("Developer API: Get configs error - %s", e)
            return []

    async def create_mqtt_config(
        self,
        name: str,
        mqtt_host: str,
        mqtt_port: int,
        mqtt_username: str,
        mqtt_password: str,
        product_code: str = PRODUCT_AIR_MONITOR_LITE,
        report_interval: int = 1,
        collect_interval: int = 1,
    ) -> int | None:
        """
        Create a new MQTT private config.
        
        Args:
            name: Config name
            mqtt_host: MQTT broker host/IP
            mqtt_port: MQTT broker port
            mqtt_username: MQTT username
            mqtt_password: MQTT password
            product_code: Product code (CGDN1 for Air Monitor Lite)
            report_interval: Report interval in minutes
            collect_interval: Collect interval in minutes
            
        Returns:
            Config ID if successful, None otherwise
        """
        if not self._token:
            _LOGGER.error("Developer API: Not logged in")
            return None
            
        try:
            session = await self._get_session()
            headers = self._get_headers(json_content=True)
            
            payload = {
                "name": name,
                "product": {"code": product_code},
                "networkConfig": {
                    "type": 1,  # 1 = Self-built MQTT
                    "mqttConfig": {
                        "endpoint": "",
                        "host": mqtt_host,
                        "port": mqtt_port,
                        "username": mqtt_username,
                        "password": mqtt_password,
                        "clientId": "qingping-{mac}",
                        "topicUp": "qingping/{mac}/up",
                        "topicDown": "qingping/{mac}/down",
                    }
                },
                "reportConfig": {
                    "reportInterval": report_interval,
                    "collectInterval": collect_interval,
                    "bleAdvInterval": 4000,
                },
                "encryptConfig": {
                    "type": 0,
                    "secretKey": "",
                },
            }
            
            async with session.post(DEV_CONFIG_URL, headers=headers, json=payload) as resp:
                result = await resp.json()
                
                if result.get("code") == 200:
                    config_id = result.get("data", {}).get("id")
                    _LOGGER.info("Developer API: Created config '%s' (ID: %s)", name, config_id)
                    return config_id
                else:
                    _LOGGER.error("Developer API: Create config failed - %s", result.get("msg"))
                    return None
                    
        except Exception as e:
            _LOGGER.error("Developer API: Create config error - %s", e)
            return None

    async def update_mqtt_config(
        self,
        config_id: int,
        name: str,
        mqtt_host: str,
        mqtt_port: int,
        mqtt_username: str,
        mqtt_password: str,
        product_code: str = PRODUCT_AIR_MONITOR_LITE,
        report_interval: int = 1,
        collect_interval: int = 1,
    ) -> bool:
        """Update an existing MQTT config."""
        if not self._token:
            return False
            
        try:
            session = await self._get_session()
            headers = self._get_headers(json_content=True)
            
            payload = {
                "id": config_id,
                "name": name,
                "product": {"code": product_code},
                "networkConfig": {
                    "type": 1,
                    "mqttConfig": {
                        "endpoint": "",
                        "host": mqtt_host,
                        "port": mqtt_port,
                        "username": mqtt_username,
                        "password": mqtt_password,
                        "clientId": "qingping-{mac}",
                        "topicUp": "qingping/{mac}/up",
                        "topicDown": "qingping/{mac}/down",
                    }
                },
                "reportConfig": {
                    "reportInterval": report_interval,
                    "collectInterval": collect_interval,
                    "bleAdvInterval": 4000,
                },
                "encryptConfig": {
                    "type": 0,
                    "secretKey": "",
                },
            }
            
            async with session.put(DEV_CONFIG_URL, headers=headers, json=payload) as resp:
                result = await resp.json()
                
                if result.get("code") == 200:
                    _LOGGER.info("Developer API: Updated config %d", config_id)
                    return True
                else:
                    _LOGGER.error("Developer API: Update config failed - %s", result.get("msg"))
                    return False
                    
        except Exception as e:
            _LOGGER.error("Developer API: Update config error - %s", e)
            return False

    async def get_devices(
        self, 
        has_private: bool = False, 
        product_code: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get list of devices.
        
        Args:
            has_private: If True, get devices WITH private config. If False, get unbound devices.
            product_code: Filter by product code (e.g. CGDN1 for Air Monitor Lite)
            
        Returns:
            List of device dictionaries
        """
        if not self._token:
            _LOGGER.error("Developer API: Not logged in")
            return []
            
        try:
            session = await self._get_session()
            headers = self._get_headers()
            
            url = f"{DEV_DEVICES_URL}?hadPrivate={str(has_private).lower()}&limit=50&offset=0"
            if product_code:
                url += f"&productCode={product_code}"
            
            async with session.get(url, headers=headers) as resp:
                result = await resp.json()
                
                if result.get("code") == 200:
                    devices = result.get("data", {}).get("devices", [])
                    _LOGGER.info("Developer API: Found %d devices (hasPrivate=%s)", 
                               len(devices), has_private)
                    return devices
                else:
                    _LOGGER.error("Developer API: Get devices failed - %s", result.get("msg"))
                    return []
                    
        except Exception as e:
            _LOGGER.error("Developer API: Get devices error - %s", e)
            return []

    async def get_unbound_air_monitors(self) -> list[dict[str, Any]]:
        """Get Air Monitor Lite devices that don't have private config yet."""
        return await self.get_devices(has_private=False, product_code=PRODUCT_AIR_MONITOR_LITE)

    async def get_bound_air_monitors(self) -> list[dict[str, Any]]:
        """Get Air Monitor Lite devices that have private config."""
        return await self.get_devices(has_private=True, product_code=PRODUCT_AIR_MONITOR_LITE)

    async def get_device_config_id(self, mac: str) -> int | None:
        """
        Get the private config ID for a specific device.
        
        Returns:
            Config ID if device is bound, None otherwise
        """
        bound_devices = await self.get_bound_air_monitors()
        
        normalized_mac = mac.upper().replace(":", "")
        for device in bound_devices:
            if device.get("mac") == normalized_mac:
                private_config = device.get("privateConfig", {})
                return private_config.get("id")
        
        return None

    async def rebind_device(self, mac: str, config_id: int) -> bool:
        """
        Rebind a device to a config (unbind first, then bind).
        
        Useful for forcing device to re-download config from cloud.
        """
        # First unbind
        if not await self.unbind_device(mac):
            _LOGGER.warning("Developer API: Could not unbind device %s, trying to bind anyway", mac)
        
        # Wait a moment
        import asyncio
        await asyncio.sleep(1)
        
        # Then bind
        return await self.bind_device_to_config(mac, config_id)

    async def bind_device_to_config(self, mac: str, config_id: int) -> bool:
        """
        Bind a device to a private config.
        
        The device will receive the MQTT config on next cloud sync.
        
        Args:
            mac: Device MAC address
            config_id: Private config ID
            
        Returns:
            True if successful
        """
        if not self._token:
            _LOGGER.error("Developer API: Not logged in")
            return False
            
        try:
            session = await self._get_session()
            headers = self._get_headers(json_content=True)
            
            payload = {
                "macList": [mac.upper().replace(":", "")],
                "privateConfigId": config_id,
            }
            
            async with session.put(DEV_DEVICES_URL, headers=headers, json=payload) as resp:
                result = await resp.json()
                
                if result.get("code") == 200:
                    _LOGGER.info("Developer API: Bound device %s to config %d", mac, config_id)
                    return True
                else:
                    _LOGGER.error("Developer API: Bind device failed - %s", result.get("msg"))
                    return False
                    
        except Exception as e:
            _LOGGER.error("Developer API: Bind device error - %s", e)
            return False

    async def bind_multiple_devices(self, macs: list[str], config_id: int) -> bool:
        """Bind multiple devices to a config at once."""
        if not self._token:
            return False
            
        try:
            session = await self._get_session()
            headers = self._get_headers(json_content=True)
            
            normalized_macs = [mac.upper().replace(":", "") for mac in macs]
            
            payload = {
                "macList": normalized_macs,
                "privateConfigId": config_id,
            }
            
            async with session.put(DEV_DEVICES_URL, headers=headers, json=payload) as resp:
                result = await resp.json()
                
                if result.get("code") == 200:
                    _LOGGER.info("Developer API: Bound %d devices to config %d", len(macs), config_id)
                    return True
                else:
                    _LOGGER.error("Developer API: Bind devices failed - %s", result.get("msg"))
                    return False
                    
        except Exception as e:
            _LOGGER.error("Developer API: Bind devices error - %s", e)
            return False

    async def unbind_device(self, mac: str) -> bool:
        """Unbind a device from its private config."""
        if not self._token:
            return False
            
        try:
            session = await self._get_session()
            headers = self._get_headers(json_content=True)
            
            normalized_mac = mac.upper().replace(":", "")
            payload = {"macList": [normalized_mac]}
            
            async with session.delete(DEV_DEVICES_URL, headers=headers, json=payload) as resp:
                result = await resp.json()
                
                if result.get("code") == 200:
                    _LOGGER.info("Developer API: Unbound device %s", mac)
                    return True
                else:
                    _LOGGER.error("Developer API: Unbind device failed - %s", result.get("msg"))
                    return False
                    
        except Exception as e:
            _LOGGER.error("Developer API: Unbind device error - %s", e)
            return False

    async def unbind_multiple_devices(self, macs: list[str]) -> bool:
        """Unbind multiple devices at once."""
        if not self._token:
            return False
            
        try:
            session = await self._get_session()
            headers = self._get_headers(json_content=True)
            
            normalized_macs = [mac.upper().replace(":", "") for mac in macs]
            payload = {"macList": normalized_macs}
            
            async with session.delete(DEV_DEVICES_URL, headers=headers, json=payload) as resp:
                result = await resp.json()
                
                if result.get("code") == 200:
                    _LOGGER.info("Developer API: Unbound %d devices", len(macs))
                    return True
                else:
                    _LOGGER.error("Developer API: Unbind devices failed - %s", result.get("msg"))
                    return False
                    
        except Exception as e:
            _LOGGER.error("Developer API: Unbind devices error - %s", e)
            return False

    async def find_or_create_config(
        self,
        mqtt_host: str,
        mqtt_port: int,
        mqtt_username: str,
        mqtt_password: str,
        config_name: str = "Home Assistant",
    ) -> int | None:
        """
        Find existing config matching MQTT settings, or create new one.
        
        Returns:
            Config ID
        """
        # First check existing configs
        configs = await self.get_configs()
        
        for config in configs:
            network_config = config.get("networkConfig", {})
            mqtt_config = network_config.get("mqttConfig", {})
            
            if (mqtt_config.get("host") == mqtt_host and 
                mqtt_config.get("port") == mqtt_port and
                mqtt_config.get("username") == mqtt_username):
                _LOGGER.info("Developer API: Found existing config '%s' (ID: %d)", 
                           config.get("name"), config.get("id"))
                return config.get("id")
        
        # Create new config
        _LOGGER.info("Developer API: No matching config found, creating new one...")
        return await self.create_mqtt_config(
            name=config_name,
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_username=mqtt_username,
            mqtt_password=mqtt_password,
        )

    async def auto_provision_devices(
        self,
        mqtt_host: str,
        mqtt_port: int,
        mqtt_username: str,
        mqtt_password: str,
        config_name: str = "Home Assistant",
    ) -> list[str]:
        """
        Automatically provision all unbound Air Monitor Lite devices.
        
        1. Find or create MQTT config
        2. Get all unbound devices
        3. Bind them to the config
        
        Returns:
            List of MACs that were provisioned
        """
        # Get or create config
        config_id = await self.find_or_create_config(
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_username=mqtt_username,
            mqtt_password=mqtt_password,
            config_name=config_name,
        )
        
        if not config_id:
            _LOGGER.error("Developer API: Could not get/create config")
            return []
        
        # Get unbound devices
        unbound = await self.get_unbound_air_monitors()
        
        if not unbound:
            _LOGGER.info("Developer API: No unbound devices found")
            return []
        
        # Bind each device
        provisioned = []
        for device in unbound:
            mac = device.get("mac")
            if mac:
                if await self.bind_device_to_config(mac, config_id):
                    provisioned.append(mac)
        
        _LOGGER.info("Developer API: Provisioned %d devices", len(provisioned))
        return provisioned
