"""Handle integration services."""

import logging
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import device_registry as dr

from .const import DLB_MODE, DOMAIN, SECTION_DLB
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
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")

    async def async_handle_stop_charging(call: ServiceCall):
        """Stop charging car."""
        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            await coordinator.async_toggle_charging(device_name, "stop")
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")

    async def async_handle_set_max_monthly_consumption(call: ServiceCall):
        """Set maximum monthly consumption."""
        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            maximum_consumption = call.data.get("maximum_consumption", None)
            await coordinator.async_set_max_monthly_consumption(device_name, maximum_consumption)
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")

    async def async_handle_set_max_session_consumption(call: ServiceCall):
        """Set maximum session consumption."""
        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            maximum_consumption = call.data.get("maximum_consumption", None)
            await coordinator.async_set_max_session_consumption(device_name, maximum_consumption)
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")

    async def async_handle_set_timer(call: ServiceCall):
        """Set charging timer."""
        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            start = call.data.get("start_time", None)
            end = call.data.get("end_time", None)
            await coordinator.async_set_timer(device_name, start, end)
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")

    async def async_handle_set_schedule(call: ServiceCall):
        """Set weekly charging schedule."""
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
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")

    async def async_handle_reset_timer(call: ServiceCall):
        """Reset charging timer."""
        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            await coordinator.async_reset_timer(device_name)
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")

    async def async_handle_set_max_current(call: ServiceCall):
        """Set maximum charging current."""
        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            max_current = call.data.get("max_current", None)
            await coordinator.async_set_max_current(device_name, max_current)
        else:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")

    async def async_handle_request_weekly_schedule(call: ServiceCall):
        """Return weekly schedule from charger."""
        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if coordinator:
            device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])
            return await coordinator.async_request_weekly_schedule(device_name)
        _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")
        return None

    async def async_handle_set_dlb_config(call: ServiceCall):
        """Set DLB operating mode and associated options.

        All parameters are optional — only supplied ones are changed.
        The coordinator preserves all other fields from its internal cache
        so a partial update never resets fields you didn't touch.
        """
        coordinator: BenyWifiUpdateCoordinator = _get_coordinator_from_device(hass, call)["coordinator"]
        if not coordinator:
            _LOGGER.error(f"Device id {call.data[ATTR_DEVICE_ID]} not found")
            return

        device_name = _get_device_name(hass, call.data[ATTR_DEVICE_ID])

        # Resolve DLB mode from string option
        dlb_mode_str = call.data.get("dlb_mode", None)
        dlb_mode = None
        if dlb_mode_str is not None:
            mode_map = {
                "pure_pv":    DLB_MODE.PURE_PV,
                "hybrid":     DLB_MODE.HYBRID,
                "full_speed": DLB_MODE.FULL_SPEED,
                "dlb_box":    DLB_MODE.DLB_BOX,
            }
            dlb_mode = mode_map.get(dlb_mode_str.lower())
            if dlb_mode is None:
                _LOGGER.error(f"Unknown dlb_mode value: {dlb_mode_str}")
                return

        await coordinator.async_set_dlb_config(
            device_name,
            dlb_enabled=call.data.get("dlb_enabled", None),
            dlb_mode=dlb_mode,
            hybrid_current=call.data.get("hybrid_current", None),
            extreme_mode=call.data.get("extreme_mode", None),
            night_mode=call.data.get("night_mode", None),
            night_start=call.data.get("night_start", None),
            night_end=call.data.get("night_end", None),
            anti_overload=call.data.get("anti_overload", None),
            anti_overload_value=call.data.get("anti_overload_value", None),
        )

    # --- Register all services ---

    standard_services = {
        "start_charging":                   async_handle_start_charging,
        "stop_charging":                    async_handle_stop_charging,
        "set_maximum_monthly_consumption":  async_handle_set_max_monthly_consumption,
        "set_maximum_session_consumption":  async_handle_set_max_session_consumption,
        "set_timer":                        async_handle_set_timer,
        "reset_timer":                      async_handle_reset_timer,
        "set_weekly_schedule":              async_handle_set_schedule,
        "set_max_current":                  async_handle_set_max_current,
    }

    for _name, _service in standard_services.items():
        hass.services.async_register(DOMAIN, _name, _service)

    # request_weekly_schedule is registered separately as it returns a value
    hass.services.async_register(
        DOMAIN,
        "request_weekly_schedule",
        async_handle_request_weekly_schedule,
        supports_response=SupportsResponse.ONLY
    )

    # Only register DLB service if at least one configured entry has DLB capability
    from .const import DLB as DLB_KEY
    has_dlb = any(
        entry_data.get("coordinator").config_entry.data.get(SECTION_DLB, {}).get(DLB_KEY, False)
        for entry_data in hass.data.get(DOMAIN, {}).values()
        if isinstance(entry_data, dict) and "coordinator" in entry_data
    )
    if has_dlb and not hass.services.has_service(DOMAIN, "set_dlb_config"):
        hass.services.async_register(DOMAIN, "set_dlb_config", async_handle_set_dlb_config)


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