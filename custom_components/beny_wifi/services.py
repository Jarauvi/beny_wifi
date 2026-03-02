"""Handle integration services."""

import logging
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import BenyWifiUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_services(hass: HomeAssistant) -> bool:
    """Set up Beny Wifi services."""

    async def async_handle_start_charging(call: ServiceCall):
        """Start charging car."""

        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            await coordinator.async_toggle_charging(device_name, "start")
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")  # noqa: G004

    async def async_handle_stop_charging(call: ServiceCall):
        """Stop charging car."""

        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            await coordinator.async_toggle_charging(device_name, "stop")
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")  # noqa: G004

    async def async_handle_set_max_monthly_consumption(call: ServiceCall):
        """Set maximum monthly consumption."""

        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            maximum_consumption = call.data.get("maximum_consumption", None)

            await coordinator.async_set_max_monthly_consumption(device_name, maximum_consumption)
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")  # noqa: G004

    async def async_handle_set_max_session_consumption(call: ServiceCall):
        """Set maximum session consumption."""

        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            maximum_consumption = call.data.get("maximum_consumption", None)

            await coordinator.async_set_max_session_consumption(device_name, maximum_consumption)
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")  # noqa: G004

    async def async_handle_set_timer(call: ServiceCall):
        """Set charging timer."""

        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            start = call.data.get("start_time", None)
            end = call.data.get("end_time", None)

            await coordinator.async_set_timer(device_name, start, end)
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")  # noqa: G004

    async def async_handle_set_schedule(call: ServiceCall):
        """Set charging timer."""

        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
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

            start = call.data.get("start_time", None)
            end = call.data.get("end_time", None)

            await coordinator.async_set_schedule(device_name, weekdays, start, end)
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")  # noqa: G004

    async def async_handle_reset_timer(call: ServiceCall):
        """Reset charging timer."""

        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            await coordinator.async_reset_timer(device_name)
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")  # noqa: G004

    async def async_handle_set_max_current(call: ServiceCall):
        """Set maximum charging current."""

        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            max_current = call.data.get("max_current", None)

            await coordinator.async_set_max_current(device_name, max_current)
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")  # noqa: G004

    async def async_handle_request_weekly_schedule(call: ServiceCall):
        """Reset charging timer."""

        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            return await coordinator.async_request_weekly_schedule(device_name)

        _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")  # noqa: G004
        return None


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

    for _name, _service in services.items():
        hass.services.async_register(DOMAIN, _name, _service)

    # async_handle_request_weekly_schedule is registered separately, because it returns value
    hass.services.async_register(
        DOMAIN,
        "request_weekly_schedule",
        async_handle_request_weekly_schedule,
        supports_response=SupportsResponse.ONLY
    )

def _get_device_name(hass: HomeAssistant, device_id: str):
    device_entry = dr.async_get(hass).async_get(device_id)
    return device_entry.name if device_entry else None

def _get_coordinator_from_device(hass: HomeAssistant, call: ServiceCall) -> BenyWifiUpdateCoordinator:
    coordinators = list(hass.data[DOMAIN].keys())
    if len(coordinators) == 1:
        return hass.data[DOMAIN][coordinators[0]]

    device_entry = dr.async_get(hass).async_get(
        call.data[ATTR_DEVICE_ID]
    )
    config_entry_ids = device_entry.config_entries
    config_entry_id = next(
        (
            config_entry_id
            for config_entry_id in config_entry_ids
            if cast(
                ConfigEntry,
                hass.config_entries.async_get_entry(config_entry_id),
            ).domain
            == DOMAIN
        ),
        None,
    )
    config_entry_unique_id = hass.config_entries.async_get_entry(config_entry_id).unique_id
    return hass.data[DOMAIN][config_entry_unique_id]