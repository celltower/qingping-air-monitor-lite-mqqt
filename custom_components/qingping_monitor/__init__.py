"""Qingping Air Monitor integration."""
from __future__ import annotations

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_API_APP_KEY, CONF_API_APP_SECRET
from .api import QingpingApiClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number", "switch", "select", "text"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Qingping Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Initialize API client if credentials provided
    api_client = None
    app_key = entry.options.get(CONF_API_APP_KEY) or entry.data.get(CONF_API_APP_KEY)
    app_secret = entry.options.get(CONF_API_APP_SECRET) or entry.data.get(CONF_API_APP_SECRET)
    
    if app_key and app_secret:
        api_client = QingpingApiClient(app_key, app_secret)
        # Test authentication
        if await api_client.authenticate():
            _LOGGER.info("Qingping Cloud API connected successfully")
        else:
            _LOGGER.warning("Qingping Cloud API authentication failed - auto-rebind disabled")
            api_client = None
    
    # Store in hass.data
    hass.data[DOMAIN][entry.entry_id] = {
        "api_client": api_client,
    }
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    _LOGGER.debug("%s: setup_entry OK: %s", DOMAIN, entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Close API client if exists
    data = hass.data[DOMAIN].get(entry.entry_id, {})
    api_client = data.get("api_client")
    if api_client:
        await api_client.close()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    
    return unload_ok
