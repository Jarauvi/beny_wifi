"""Initialize integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from .const import (
    CONF_ANTI_OVERLOAD,
    CONF_ANTI_OVERLOAD_VALUE,
    DEFAULT_ANTI_OVERLOAD,
    DEFAULT_ANTI_OVERLOAD_VALUE,
    DOMAIN, 
    IP_ADDRESS, 
    PLATFORMS, 
    PORT, 
    DEFAULT_PORT,
    SCAN_INTERVAL, 
    DLB, 
    CONF_MAX_CURRENT_MIN, 
    CONF_MAX_CURRENT_MAX, 
    DEFAULT_MAX_CURRENT_MIN, 
    DEFAULT_MAX_CURRENT_MAX,
    SERIAL,
    CONF_SERIAL,
    CONF_PIN,
    DEFAULT_SCAN_INTERVAL,
    SECTION_CONNECTION,
    SECTION_DEVICE,
    SECTION_CURRENT_LIMITS,
    SECTION_DLB,
    get_config_parameter
)
from .coordinator import BenyWifiUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Beny Wifi from a config entry."""
    _LOGGER.info("Setting up Beny WiFi integration")
    
    # Workaround to set existing unique id as the serial
    serial = get_config_parameter(entry, SECTION_DEVICE, SERIAL) or get_config_parameter(entry, SECTION_DEVICE, CONF_SERIAL)
    if serial:
        serial_str = str(serial)
        # If unique_id is missing or doesn't match the serial string
        if entry.unique_id != serial_str:
            hass.config_entries.async_update_entry(entry, unique_id=serial_str)
    
    
    ip_address = get_config_parameter(entry, SECTION_CONNECTION, IP_ADDRESS)
    port = get_config_parameter(entry, SECTION_CONNECTION, PORT)
    # Use DEFAULT_SCAN_INTERVAL (30 seconds) if not configured
    scan_interval = get_config_parameter(entry, SECTION_CONNECTION, SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
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

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1 or config_entry.version == 2:
        new_data = {**config_entry.data}
        
        new_data[SECTION_CONNECTION] = {
            PORT: config_entry.data.get(PORT, DEFAULT_PORT),
            IP_ADDRESS: config_entry.data.get(IP_ADDRESS, ""),
            SCAN_INTERVAL: config_entry.data.get(SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        }
        new_data[SECTION_DEVICE] = {
            CONF_SERIAL: config_entry.data.get(CONF_SERIAL, ""),
            CONF_PIN: config_entry.data.get(CONF_PIN, ""),
            DLB: config_entry.data.get(DLB, False),
        }
        new_data[SECTION_CURRENT_LIMITS] = {
            CONF_MAX_CURRENT_MIN: config_entry.data.get(CONF_MAX_CURRENT_MIN, DEFAULT_MAX_CURRENT_MIN),
            CONF_MAX_CURRENT_MAX: config_entry.data.get(CONF_MAX_CURRENT_MAX, DEFAULT_MAX_CURRENT_MAX),  
        }
        # Seed DLB section with defaults — Anti Overload was not configurable in v1/v2
        new_data[SECTION_DLB] = {
            DLB: config_entry.data.get(DLB, False),
            CONF_ANTI_OVERLOAD: DEFAULT_ANTI_OVERLOAD,
            CONF_ANTI_OVERLOAD_VALUE: DEFAULT_ANTI_OVERLOAD_VALUE,
        }
        
        # Update the entry with new sectioned data and version
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=3)

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True