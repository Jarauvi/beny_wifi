"""Button entities for Beny Wifi."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, MODEL, SERIAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up button platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_id = config_entry.data[SERIAL]
    device_model = config_entry.data[MODEL]

    buttons = [
        BenyWifiSendMaxCurrentButton(
            coordinator,
            "send_max_current",
            device_id=device_id,
            device_model=device_model,
        ),
        BenyWifiStartChargingButton(
            coordinator,
            "start_charging",
            device_id=device_id,
            device_model=device_model,
        ),
        BenyWifiStopChargingButton(
            coordinator,
            "stop_charging",
            device_id=device_id,
            device_model=device_model,
        ),
    ]

    async_add_entities(buttons)


class BenyWifiSendMaxCurrentButton(ButtonEntity):
    """Button to send max current value to the charger."""

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize the button entity."""
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self.entity_id = f"button.{device_id}_{key}"
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:send"

    @property
    def unique_id(self):
        """Return a unique ID for this button entity."""
        return f"{self._device_id}_{self.key}"

    async def async_press(self) -> None:
        """Handle the button press - send current max_current value to device."""
        # Try multiple entity_id formats to find the number entity
        possible_entity_ids = [
            f"number.{self._device_id}_max_current_control",
            f"number.beny_charger_{self._device_id}_max_current_control",
        ]
        
        number_state = None
        used_entity_id = None
        
        # Try to find the number entity
        for entity_id in possible_entity_ids:
            number_state = self.hass.states.get(entity_id)
            if number_state is not None:
                used_entity_id = entity_id
                _LOGGER.debug(f"Found number entity: {entity_id}")
                break
        
        # If not found by entity_id, search through all number entities
        if number_state is None:
            _LOGGER.warning(
                f"Could not find number entity by standard IDs. Searching all number entities..."
            )
            for state in self.hass.states.async_all("number"):
                if "max_current_control" in state.entity_id and self._device_id in state.entity_id:
                    number_state = state
                    used_entity_id = state.entity_id
                    _LOGGER.info(f"Found number entity by search: {state.entity_id}")
                    break
        
        if number_state is None:
            _LOGGER.error(
                f"Could not find number entity for device {self._device_id}. "
                f"Tried: {', '.join(possible_entity_ids)}. "
                f"Available number entities: {[s.entity_id for s in self.hass.states.async_all('number')]}"
            )
            return
        
        try:
            max_current = int(float(number_state.state))
            
            # Validate range against the number entity's own min/max
            number_entity = None
            for domain_data in self.hass.data.get("beny_wifi", {}).values():
                pass  # coordinator is in domain_data but we just use the state bounds below

            min_val = int(float(number_state.attributes.get("min", 6)))
            max_val = int(float(number_state.attributes.get("max", 32)))

            if not (min_val <= max_current <= max_val):
                _LOGGER.error(
                    f"Max current value {max_current}A is out of range ({min_val}-{max_val}A)"
                )
                return
            
            # Send to device using coordinator
            device_name = f"Beny Charger {self._device_id}"
            await self.coordinator.async_set_max_current(device_name, max_current)
            
            _LOGGER.info(
                f"Successfully sent max current {max_current}A to {device_name} "
                f"(read from {used_entity_id})"
            )
            
        except (ValueError, TypeError) as e:
            _LOGGER.error(
                f"Error converting max current value from {used_entity_id}: "
                f"state={number_state.state}, error: {e}"
            )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"Beny Charger {self._device_id}",
            manufacturer="ZJ Beny",
            model=self._device_model,
            serial_number=self._device_id,
        )

class BenyWifiStartChargingButton(ButtonEntity):
    """Button to start charging."""

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize the button entity."""
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self.entity_id = f"button.{device_id}_{key}"
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:power-plug"

    @property
    def unique_id(self):
        """Return a unique ID for this button entity."""
        return f"{self._device_id}_{self.key}"

    async def async_press(self) -> None:
        """Handle the button press - send start charging command to device."""
        device_name = f"Beny Charger {self._device_id}"
        await self.coordinator.async_toggle_charging(device_name, "start")
        _LOGGER.info(f"Start charging button pressed for {device_name}")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"Beny Charger {self._device_id}",
            manufacturer="ZJ Beny",
            model=self._device_model,
            serial_number=self._device_id,
        )


class BenyWifiStopChargingButton(ButtonEntity):
    """Button to stop charging."""

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize the button entity."""
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self.entity_id = f"button.{device_id}_{key}"
        self._attr_has_entity_name = True
        self._attr_icon = "mdi:power-plug-off"

    @property
    def unique_id(self):
        """Return a unique ID for this button entity."""
        return f"{self._device_id}_{self.key}"

    async def async_press(self) -> None:
        """Handle the button press - send stop charging command to device."""
        device_name = f"Beny Charger {self._device_id}"
        await self.coordinator.async_toggle_charging(device_name, "stop")
        _LOGGER.info(f"Stop charging button pressed for {device_name}")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"Beny Charger {self._device_id}",
            manufacturer="ZJ Beny",
            model=self._device_model,
            serial_number=self._device_id,
        )