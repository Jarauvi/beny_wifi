"""Number entities for Beny Wifi."""

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CHARGER_TYPE, DLB, DOMAIN, MODEL, SERIAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up number platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_id = config_entry.data[SERIAL]
    device_model = config_entry.data[MODEL]

    numbers = [
        BenyWifiMaxCurrentNumber(
            coordinator, 
            "max_current_control", 
            device_id=device_id, 
            device_model=device_model
        )
    ]

    async_add_entities(numbers, update_before_add=True)
    _LOGGER.info(f"Added max_current_control number entity for device {device_id}")


class BenyWifiMaxCurrentNumber(CoordinatorEntity, NumberEntity):
    """Max Current control number entity."""

    _attr_available = True

    def __init__(self, coordinator, key, device_id=None, device_model=None):
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.key = key
        self._attr_translation_key = key
        self._device_id = device_id
        self._device_model = device_model
        self._attr_has_entity_name = True
        
        # Number entity configuration
        self._attr_native_min_value = 6
        self._attr_native_max_value = 32
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:current-ac"
        
        # Store the local value separately from coordinator data
        self._local_value = None
        
        # Set entity_id explicitly
        self.entity_id = f"number.{device_id}_max_current_control"

    @property
    def unique_id(self):
        """Return a unique ID for this number entity."""
        return f"{self._device_id}_{self.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def native_value(self):
        """Return the current value - prefer local value, fall back to coordinator."""
        # If we have a local value set by the user, return that
        if self._local_value is not None:
            return float(self._local_value)
        
        # Otherwise try to get from coordinator data
        if self.coordinator.data:
            max_current = self.coordinator.data.get("max_current")
            if max_current is not None:
                try:
                    return float(max_current)
                except (ValueError, TypeError):
                    _LOGGER.warning(f"Invalid max_current value from coordinator: {max_current}")
        
        # Final fallback
        return 16.0

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value - this stores it locally but doesn't send to device."""
        self._local_value = int(value)
        self.async_write_ha_state()
        _LOGGER.info(f"Max current control for {self._device_id} set to {int(value)}A (stored locally, press Send button to apply)")

    @property
    def should_poll(self) -> bool:
        """No need to poll, coordinator handles updates."""
        return False

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