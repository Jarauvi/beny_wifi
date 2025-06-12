"""Handle integration services."""

import logging
from typing import cast, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import BenyWifiUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant, coordinator: BenyWifiUpdateCoordinator) -> None:
    """Set up Beny Wifi services."""

    async def async_handle_start_charging(call: ServiceCall):
        coordinator_entry = _get_coordinator_from_device(hass, call)
        if not coordinator_entry:
            _log_device_not_found(call)
            return
        device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
        await coordinator_entry.async_toggle_charging(device_name, "start")

    async def async_handle_stop_charging(call: ServiceCall):
        coordinator_entry = _get_coordinator_from_device(hass, call)
        if not coordinator_entry:
            _log_device_not_found(call)
            return
        device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
        await coordinator_entry.async_toggle_charging(device_name, "stop")

    async def async_handle_set_max_monthly_consumption(call: ServiceCall):
        coordinator_entry = _get_coordinator_from_device(hass, call)
        if not coordinator_entry:
            _log_device_not_found(call)
            return
        device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
        maximum_consumption = call.data.get("maximum_consumption")
        await coordinator_entry.async_set_max_monthly_consumption(device_name, maximum_consumption)

    async def async_handle_set_max_session_consumption(call: ServiceCall):
        coordinator_entry = _get_coordinator_from_device(hass, call)
        if not coordinator_entry:
            _log_device_not_found(call)
            return
        device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
        maximum_consumption = call.data.get("maximum_consumption")
        await coordinator_entry.async_set_max_session_consumption(device_name, maximum_consumption)

    async def async_handle_set_timer(call: ServiceCall):
        coordinator_entry = _get_coordinator_from_device(hass, call)
        if not coordinator_entry:
            _log_device_not_found(call)
            return
        device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
        start = call.data.get("start_time")
        end = call.data.get("end_time")
        await coordinator_entry.async_set_timer(device_name, start, end)

    async def async_handle_reset_timer(call: ServiceCall):
        coordinator_entry = _get_coordinator_from_device(hass, call)
        if not coordinator_entry:
            _log_device_not_found(call)
            return
        device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
        await coordinator_entry.async_reset_timer(device_name)

    async def async_handle_set_schedule(call: ServiceCall):
        coordinator_entry = _get_coordinator_from_device(hass, call)
        if not coordinator_entry:
            _log_device_not_found(call)
            return
        device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
        weekdays = [
            call.data.get("sunday"),
            call.data.get("monday"),
            call.data.get("tuesday"),
            call.data.get("wednesday"),
            call.data.get("thursday"),
            call.data.get("friday"),
            call.data.get("saturday")
        ]
        start = call.data.get("start_time")
        end = call.data.get("end_time")
        await coordinator_entry.async_set_schedule(device_name, weekdays, start, end)

    async def async_handle_request_weekly_schedule(call: ServiceCall):
        coordinator_entry = _get_coordinator_from_device(hass, call)
        if not coordinator_entry:
            _log_device_not_found(call)
            return None
        device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
        return await coordinator_entry.async_request_weekly_schedule(device_name)

    async def async_handle_set_max_current(call: ServiceCall):
        device_name = call.data.get("device_name", "Beny Charger")
        max_current = call.data["max_current"]
        await coordinator.async_set_max_current(device_name, max_current)

    # Register all services
    services = {
        "start_charging": async_handle_start_charging,
        "stop_charging": async_handle_stop_charging,
        "set_maximum_monthly_consumption": async_handle_set_max_monthly_consumption,
        "set_maximum_session_consumption": async_handle_set_max_session_consumption,
        "set_timer": async_handle_set_timer,
        "reset_timer": async_handle_reset_timer,
        "set_weekly_schedule": async_handle_set_schedule,
        "set_max_current": async_handle_set_max_current,
    }

    for name, handler in services.items():
        hass.services.async_register(DOMAIN, name, handler)
        _LOGGER.debug(f"Registered service: {DOMAIN}.{name}")

    hass.services.async_register(
        DOMAIN,
        "request_weekly_schedule",
        async_handle_request_weekly_schedule,
        supports_response=SupportsResponse.ONLY,
    )
    _LOGGER.debug(f"Registered service: {DOMAIN}.request_weekly_schedule")


def _get_device_name(hass: HomeAssistant, device_id: str) -> Optional[str]:
    device_entry = dr.async_get(hass).async_get(device_id)
    return device_entry.name if device_entry else None


def _get_coordinator_from_device(hass: HomeAssistant, call: ServiceCall) -> Optional[BenyWifiUpdateCoordinator]:
    coordinators = list(hass.data[DOMAIN].values())

    if len(coordinators) == 1:
        return coordinators[0]["coordinator"]

    device_entry = dr.async_get(hass).async_get(call.data[ATTR_DEVICE_ID])
    if not device_entry:
        return None

    for config_entry_id in device_entry.config_entries:
        config_entry = hass.config_entries.async_get_entry(config_entry_id)
        if config_entry and config_entry.domain == DOMAIN:
            return hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    return None


def _log_device_not_found(call: ServiceCall) -> None:
    _LOGGER.error(f"Device ID {call.data.get(ATTR_DEVICE_ID)} not found")
