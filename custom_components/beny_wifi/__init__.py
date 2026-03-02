"""Initialize integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN, IP_ADDRESS, PLATFORMS, PORT, SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .coordinator import BenyWifiUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Beny Wifi from a config entry."""
    _LOGGER.info("Setting up Beny WiFi integration")
    
    ip_address = entry.data[IP_ADDRESS]
    port = entry.data[PORT]
    # Use DEFAULT_SCAN_INTERVAL (30 seconds) if not configured
    scan_interval = entry.data.get(SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    _LOGGER.info(f"Using scan interval: {scan_interval} seconds")
    
    # FIXED: Pass entry as the second parameter
    coordinator = BenyWifiUpdateCoordinator(hass, entry, ip_address, port, scan_interval)
    
    # Perform the first update to ensure connection works
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as ex:
        _LOGGER.error(f"Error setting up coordinator: {ex}")
        raise ConfigEntryNotReady from ex
    
    # Store the coordinator for use by platforms
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }
    
    # Forward entry setup to supported platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # setup services
    await async_setup_services(hass)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Beny WiFi integration")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Clean up resources
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok