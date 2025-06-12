"""Initialize integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, IP_ADDRESS, PLATFORMS, PORT, SCAN_INTERVAL
from .coordinator import BenyWifiUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Beny Wifi from a config entry."""
    _LOGGER.info("Setting up Beny WiFi integration")

    ip_address = entry.data[IP_ADDRESS]
    port = entry.data[PORT]
    scan_interval = entry.data[SCAN_INTERVAL]

    # Create the DataUpdateCoordinator
    coordinator = BenyWifiUpdateCoordinator(hass, ip_address, port, scan_interval)

    # Perform the first update to ensure connection works
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as ex:
        _LOGGER.error(f"Error setting up coordinator: {ex}")  # noqa: G004
        raise ConfigEntryNotReady from ex

    # Store the coordinator for use by platforms
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    # Forward entry setup to supported platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # setup services
    await async_setup_services(hass, coordinator)
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
