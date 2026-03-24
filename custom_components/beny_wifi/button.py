"""Button entities for Beny Wifi."""

import logging
from homeassistant.helpers import entity_registry as er
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN, 
    MODEL, 
    SERIAL,
    SECTION_DEVICE,
    get_device_id,
    get_entity_state_by_key,
    get_config_parameter
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up button platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    serial = get_config_parameter(config_entry, SECTION_DEVICE, SERIAL)
    device_model = get_config_parameter(config_entry, SECTION_DEVICE, MODEL)

    buttons = [
        BenyWifiSendMaxCurrentButton(
            coordinator,
            "send_max_current",
            serial=serial,
            device_model=device_model,
            config_entry=config_entry
        ),
        BenyWifiStartChargingButton(
            coordinator,
            "start_charging",
            serial=serial,
            device_model=device_model,
            config_entry=config_entry
        ),
        BenyWifiStopChargingButton(
            coordinator,
            "stop_charging",
            serial=serial,
            device_model=device_model,
            config_entry=config_entry
            
        ),
    ]

    async_add_entities(buttons)

class BenyWifiBaseButton(ButtonEntity):
    """Base class for Beny buttons to handle shared attributes."""
    _attr_has_entity_name = True
    
    def __init__(self, coordinator, key, serial, device_model, config_entry):
        self.coordinator = coordinator
        self._serial = serial
        self._device_model = device_model
        self.key = key
        self._attr_translation_key = key
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_suggested_object_id = key
        self._config_entry = config_entry
              
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers = {(DOMAIN, self._serial)},
            name = get_device_id(self.hass, self._serial, self._device_model),
            manufacturer = "ZJ Beny",
            model = self._device_model,
            serial_number=self._serial
        )

class BenyWifiSendMaxCurrentButton(BenyWifiBaseButton):
    """Button to send max current value to the charger."""
    _attr_icon = "mdi:send"

    async def async_press(self) -> None:
        """Handle the button press - send current max_current value to device."""
        # Find entity from entity registry
        number_state = get_entity_state_by_key(self.hass, self._config_entry, "max_current_control", "number")
        
        if number_state is None or number_state.state in ("unknown", "unavailable"):
            _LOGGER.error("Number entity %s has no valid state", number_entity_id)
            return
        
        try:
            max_current = int(float(number_state.state))
            

            min_val = int(float(number_state.attributes.get("min", 6)))
            max_val = int(float(number_state.attributes.get("max", 32)))

            if not (min_val <= max_current <= max_val):
                _LOGGER.error(
                    f"Max current value {max_current}A is out of range ({min_val}-{max_val}A)"
                )
                return
            
            # Send to device using coordinator
            device_name = get_device_id(self.hass, self._serial, self._device_model)
            await self.coordinator.async_set_max_current(device_name, max_current)
            
            _LOGGER.info(
                f"Successfully sent max current {max_current}A to {device_name} "
            )
            
        except (ValueError, TypeError) as e:
            _LOGGER.error(
                f"Error converting max current value from {number_entity_id}: "
                f"state={number_state.state}, error: {e}"
            )

class BenyWifiStartChargingButton(BenyWifiBaseButton):
    """Button to start charging."""
    _attr_icon = "mdi:power-plug"

    async def async_press(self) -> None:
        """Handle the button press - send start charging command to device."""
        device_name = get_device_id(self.hass, self._serial, self._device_model)
        await self.coordinator.async_toggle_charging(device_name, "start")
        _LOGGER.info(f"Start charging button pressed for {device_name}")

class BenyWifiStopChargingButton(BenyWifiBaseButton):
    """Button to stop charging."""
    _attr_icon = "mdi:power-plug-off"

    async def async_press(self) -> None:
        """Handle the button press - send stop charging command to device."""
        device_name = get_device_id(self.hass, self._serial, self._device_model)
        await self.coordinator.async_toggle_charging(device_name, "stop")
        _LOGGER.info(f"Stop charging button pressed for {device_name}")